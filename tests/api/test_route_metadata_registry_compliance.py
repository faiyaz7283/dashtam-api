"""Registry compliance tests - prevent drift and ensure completeness.

These tests ensure the Route Metadata Registry remains the single source of truth
by validating that:
1. All FastAPI routes are registered in the registry (no orphans)
2. All registry entries generate actual routes (no dead entries)
3. Auth policies are enforced correctly
4. Rate limit rules cover all endpoints
5. Metadata is consistent across layers

If these tests fail, it means the registry has drifted from actual implementation.
"""

from src.infrastructure.rate_limit.config import RATE_LIMIT_RULES
from src.presentation.routers.api.v1 import v1_router
from src.presentation.routers.api.v1.routes.derivations import build_rate_limit_rules
from src.presentation.routers.api.v1.routes.metadata import AuthLevel, RateLimitPolicy
from src.presentation.routers.api.v1.routes.registry import ROUTE_REGISTRY


# =============================================================================
# Test Class 1: Route Completeness
# =============================================================================


class TestRegistryCompleteness:
    """Verify registry and FastAPI routes are in sync."""

    def test_all_routes_are_registered(self):
        """Every FastAPI route must have a registry entry.

        Fails if: Someone adds a route without registering it in ROUTE_REGISTRY.
        """
        # Extract actual routes from FastAPI router
        actual_routes = set()
        for route in v1_router.routes:
            # Skip non-endpoint routes (docs, openapi, etc.)
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    # Normalize path (FastAPI includes /api/v1 prefix)
                    path = route.path
                    endpoint_key = f"{method} {path}"
                    actual_routes.add(endpoint_key)

        # Extract expected routes from registry
        expected_routes = set()
        for entry in ROUTE_REGISTRY:
            endpoint_key = f"{entry.method.value} /api/v1{entry.path}"
            expected_routes.add(endpoint_key)

        # Find missing and extra routes
        missing_in_registry = actual_routes - expected_routes
        missing_in_fastapi = expected_routes - actual_routes

        # Filter out FastAPI-added routes (HEAD for GET, OPTIONS)
        ignored_methods = {"HEAD", "OPTIONS"}
        missing_in_registry = {
            r
            for r in missing_in_registry
            if not any(r.startswith(m) for m in ignored_methods)
        }

        # Assert 1:1 mapping
        assert not missing_in_registry, (
            f"Routes exist in FastAPI but not in ROUTE_REGISTRY: {missing_in_registry}. "
            "Add these routes to registry.py or remove from router."
        )

        assert not missing_in_fastapi, (
            f"Routes exist in ROUTE_REGISTRY but not in FastAPI: {missing_in_fastapi}. "
            "Check route generation in generator.py."
        )

    def test_operation_ids_are_unique(self):
        """Every operation_id must be unique across all routes.

        Fails if: Duplicate operation_id in registry (breaks OpenAPI spec).
        """
        operation_ids = [entry.operation_id for entry in ROUTE_REGISTRY]
        duplicates = [
            op_id for op_id in set(operation_ids) if operation_ids.count(op_id) > 1
        ]

        assert not duplicates, (
            f"Duplicate operation_ids found: {duplicates}. "
            "Each route must have a unique operation_id."
        )

    def test_all_handlers_are_callable(self):
        """Every handler in registry must be a callable function.

        Fails if: Someone registers a non-function as handler.
        """
        for entry in ROUTE_REGISTRY:
            assert callable(entry.handler), (
                f"Route '{entry.method.value} {entry.path}' has non-callable handler: "
                f"{entry.handler}. Handler must be a function."
            )

    def test_all_routes_have_tags(self):
        """Every route must have at least one tag for OpenAPI grouping.

        Fails if: Route has empty tags list.
        """
        for entry in ROUTE_REGISTRY:
            assert entry.tags and len(entry.tags) > 0, (
                f"Route '{entry.method.value} {entry.path}' has no tags. "
                "Add at least one tag for OpenAPI documentation grouping."
            )

    def test_all_routes_have_operation_id(self):
        """Every route must have an operation_id.

        Fails if: Route has None or empty operation_id.
        """
        for entry in ROUTE_REGISTRY:
            assert entry.operation_id, (
                f"Route '{entry.method.value} {entry.path}' has no operation_id. "
                "Add unique operation_id for OpenAPI client generation."
            )

    def test_all_routes_have_resource_name(self):
        """Every route must have a resource name.

        Fails if: Route has None or empty resource field.
        """
        for entry in ROUTE_REGISTRY:
            assert entry.resource, (
                f"Route '{entry.method.value} {entry.path}' has no resource name. "
                "Add resource field for grouping and documentation."
            )


# =============================================================================
# Test Class 2: Auth Policy Enforcement
# =============================================================================


class TestAuthPolicyEnforcement:
    """Verify auth policies are correctly enforced."""

    def test_public_routes_have_no_auth_dependencies(self):
        """PUBLIC routes should not inject auth dependencies.

        Fails if: PUBLIC route has AuthenticatedUser/CurrentUser dependency.
        """
        for entry in ROUTE_REGISTRY:
            if entry.auth_policy.level == AuthLevel.PUBLIC:
                # Check handler signature for auth dependencies
                import inspect

                sig = inspect.signature(entry.handler)

                for param_name, param in sig.parameters.items():
                    param_annotation = str(param.annotation)
                    assert "CurrentUser" not in param_annotation, (
                        f"PUBLIC route '{entry.method.value} {entry.path}' "
                        f"has CurrentUser dependency in parameter '{param_name}'. "
                        "PUBLIC routes should not require authentication."
                    )

    def test_authenticated_routes_have_auth_or_manual(self):
        """AUTHENTICATED routes must have auth dependency OR be MANUAL_AUTH.

        Fails if: AUTHENTICATED route has no auth mechanism.
        """
        for entry in ROUTE_REGISTRY:
            if entry.auth_policy.level == AuthLevel.AUTHENTICATED:
                import inspect

                sig = inspect.signature(entry.handler)

                # Check if handler has CurrentUser or is MANUAL_AUTH
                has_auth_dependency = any(
                    "CurrentUser" in str(param.annotation)
                    for param in sig.parameters.values()
                )

                # MANUAL_AUTH routes handle auth themselves
                is_manual_auth = entry.auth_policy.level == AuthLevel.MANUAL_AUTH  # type: ignore[comparison-overlap]

                # Either has dependency OR is manual (but not both in this case)
                assert has_auth_dependency or is_manual_auth, (
                    f"AUTHENTICATED route '{entry.method.value} {entry.path}' "
                    f"has no CurrentUser dependency. Add CurrentUser parameter "
                    f"or change auth_policy to MANUAL_AUTH."
                )

    def test_manual_auth_routes_have_rationale(self):
        """MANUAL_AUTH routes must document why they're manual.

        Fails if: MANUAL_AUTH route has no rationale comment.
        """
        manual_auth_routes = [
            entry
            for entry in ROUTE_REGISTRY
            if entry.auth_policy.level == AuthLevel.MANUAL_AUTH
        ]

        for entry in manual_auth_routes:
            assert entry.auth_policy.rationale, (
                f"MANUAL_AUTH route '{entry.method.value} {entry.path}' "
                f"has no rationale. Add rationale to AuthPolicy explaining "
                f"why this route handles auth manually."
            )

            # Rationale should be meaningful (not just a placeholder)
            assert len(entry.auth_policy.rationale) > 10, (
                f"MANUAL_AUTH route '{entry.method.value} {entry.path}' "
                f"has insufficient rationale: '{entry.auth_policy.rationale}'. "
                f"Provide detailed explanation."
            )


# =============================================================================
# Test Class 3: Rate Limit Coverage
# =============================================================================


class TestRateLimitCoverage:
    """Verify rate limits are complete and consistent."""

    def test_all_registry_entries_have_rate_limit_policy(self):
        """Every registry entry must have a rate_limit_policy.

        Fails if: Someone forgets to set rate_limit_policy.
        """
        for entry in ROUTE_REGISTRY:
            assert entry.rate_limit_policy is not None, (
                f"Route '{entry.method.value} {entry.path}' "
                f"has no rate_limit_policy. Add a rate limit policy."
            )

    def test_rate_limit_rules_have_positive_values(self):
        """Generated rate limit rules must have valid positive values.

        Fails if: Rule has zero or negative max_tokens, refill_rate, or cost.
        """
        for endpoint, rule in RATE_LIMIT_RULES.items():
            assert rule.max_tokens > 0, (
                f"Rate limit rule for '{endpoint}' has invalid max_tokens: {rule.max_tokens}. "
                "Must be positive integer."
            )
            assert rule.refill_rate > 0, (
                f"Rate limit rule for '{endpoint}' has invalid refill_rate: {rule.refill_rate}. "
                "Must be positive number."
            )
            assert rule.cost > 0, (
                f"Rate limit rule for '{endpoint}' has invalid cost: {rule.cost}. "
                "Must be positive integer."
            )

    def test_rate_limit_rules_cover_all_registry_entries(self):
        """Generated rate limit rules must cover all registry entries.

        Fails if: build_rate_limit_rules() doesn't generate rule for an entry.
        """
        generated_rules = build_rate_limit_rules(ROUTE_REGISTRY)

        for entry in ROUTE_REGISTRY:
            endpoint_key = f"{entry.method.value} /api/v1{entry.path}"
            assert endpoint_key in generated_rules, (
                f"No rate limit rule generated for '{endpoint_key}'. "
                f"Check build_rate_limit_rules() in derivations.py."
            )

    def test_no_orphaned_rate_limit_rules(self):
        """Rate limit rules should only exist for registered routes.

        Fails if: Rate limit rule exists for non-existent endpoint.
        """
        registry_endpoints = {
            f"{entry.method.value} /api/v1{entry.path}" for entry in ROUTE_REGISTRY
        }

        for rule_endpoint in RATE_LIMIT_RULES.keys():
            assert rule_endpoint in registry_endpoints, (
                f"Rate limit rule exists for unregistered endpoint: '{rule_endpoint}'. "
                f"Remove orphaned rule or add route to registry."
            )


# =============================================================================
# Test Class 4: Metadata Consistency
# =============================================================================


class TestMetadataConsistency:
    """Verify metadata is consistent across layers."""

    def test_registry_matches_fastapi_routes(self):
        """Registry metadata should match generated FastAPI routes.

        Fails if: Generator doesn't properly translate registry to FastAPI.
        """
        # Build map of FastAPI routes
        fastapi_routes = {}
        for route in v1_router.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    if method not in {"HEAD", "OPTIONS"}:
                        key = f"{method} {route.path}"
                        fastapi_routes[key] = route

        # Verify each registry entry
        for entry in ROUTE_REGISTRY:
            endpoint_key = f"{entry.method.value} /api/v1{entry.path}"

            assert endpoint_key in fastapi_routes, (
                f"Registry entry '{endpoint_key}' not found in FastAPI routes"
            )

            fastapi_route = fastapi_routes[endpoint_key]

            # Verify metadata matches
            if hasattr(fastapi_route, "summary"):
                assert fastapi_route.summary == entry.summary, (
                    f"Summary mismatch for '{endpoint_key}': "
                    f"Registry='{entry.summary}', FastAPI='{fastapi_route.summary}'"
                )

            if hasattr(fastapi_route, "status_code"):
                assert fastapi_route.status_code == entry.status_code, (
                    f"Status code mismatch for '{endpoint_key}': "
                    f"Registry={entry.status_code}, FastAPI={fastapi_route.status_code}"
                )

    def test_response_models_are_defined(self):
        """All non-204 routes should have response_model defined.

        Fails if: Route returns data but has no response schema.

        Note: SSE streaming endpoints (RateLimitPolicy.SSE_STREAM) are exempt
        because they return StreamingResponse, not Pydantic models.
        """
        for entry in ROUTE_REGISTRY:
            # 204 No Content doesn't need response model
            if entry.status_code == 204:
                assert entry.response_model is None, (
                    f"Route '{entry.method.value} {entry.path}' "
                    f"has 204 status but defines response_model. "
                    f"204 No Content should have response_model=None."
                )
            # SSE streaming endpoints return StreamingResponse, not Pydantic model
            elif entry.rate_limit_policy == RateLimitPolicy.SSE_STREAM:
                assert entry.response_model is None, (
                    f"Route '{entry.method.value} {entry.path}' "
                    f"is SSE streaming but defines response_model. "
                    f"SSE endpoints use StreamingResponse and should have response_model=None."
                )
            else:
                # Other status codes should have response model
                assert entry.response_model is not None, (
                    f"Route '{entry.method.value} {entry.path}' "
                    f"returns {entry.status_code} but has no response_model. "
                    f"Define a response schema in src/schemas/."
                )

    def test_error_specs_are_valid(self):
        """All error specs must have valid status codes.

        Fails if: ErrorSpec has invalid or non-error HTTP status code.
        """
        valid_error_statuses = {400, 401, 403, 404, 409, 415, 422, 429, 500, 502, 503}

        for entry in ROUTE_REGISTRY:
            if entry.errors is None:
                continue
            for error_spec in entry.errors:
                assert error_spec.status in valid_error_statuses, (
                    f"Route '{entry.method.value} {entry.path}' "
                    f"has invalid error status: {error_spec.status}. "
                    f"Must be one of: {valid_error_statuses}"
                )
                assert error_spec.description, (
                    f"Route '{entry.method.value} {entry.path}' "
                    f"has ErrorSpec with status {error_spec.status} but no description. "
                    f"Add description for OpenAPI documentation."
                )

    def test_path_parameters_match_handler_signature(self):
        """Path parameters in route must exist in handler signature.

        Fails if: Path has {param} but handler doesn't accept param.
        """
        import re
        import inspect

        for entry in ROUTE_REGISTRY:
            # Extract path parameters (e.g., {user_id} from /users/{user_id})
            path_params = re.findall(r"\{(\w+)\}", entry.path)

            if path_params:
                sig = inspect.signature(entry.handler)
                handler_params = set(sig.parameters.keys())

                missing_params = set(path_params) - handler_params
                assert not missing_params, (
                    f"Route '{entry.method.value} {entry.path}' "
                    f"has path parameters {missing_params} not in handler signature. "
                    f"Handler parameters: {handler_params}"
                )


# =============================================================================
# Test Class 5: Registry Statistics
# =============================================================================


class TestRegistryStatistics:
    """Report registry statistics for visibility."""

    def test_registry_statistics(self):
        """Report comprehensive registry statistics.

        This test always passes - it's informational only.
        """
        # Count by method
        method_counts: dict[str, int] = {}
        for entry in ROUTE_REGISTRY:
            method = entry.method.value
            method_counts[method] = method_counts.get(method, 0) + 1

        # Count by auth policy
        auth_counts: dict[str, int] = {}
        for entry in ROUTE_REGISTRY:
            level = entry.auth_policy.level.value
            auth_counts[level] = auth_counts.get(level, 0) + 1

        # Count by rate limit policy
        rate_limit_counts: dict[str, int] = {}
        for entry in ROUTE_REGISTRY:
            policy = entry.rate_limit_policy.value
            rate_limit_counts[policy] = rate_limit_counts.get(policy, 0) + 1

        # Count by idempotency
        idempotency_counts: dict[str, int] = {}
        for entry in ROUTE_REGISTRY:
            level = entry.idempotency.value
            idempotency_counts[level] = idempotency_counts.get(level, 0) + 1

        # Build report
        report = [
            "\n" + "=" * 60,
            "ROUTE METADATA REGISTRY STATISTICS",
            "=" * 60,
            f"Total Endpoints: {len(ROUTE_REGISTRY)}",
            "",
            "HTTP Methods:",
            *[
                f"  {method}: {count}"
                for method, count in sorted(method_counts.items())
            ],
            "",
            "Auth Policies:",
            *[f"  {policy}: {count}" for policy, count in sorted(auth_counts.items())],
            "",
            "Rate Limit Policies:",
            *[
                f"  {policy}: {count}"
                for policy, count in sorted(rate_limit_counts.items())
            ],
            "",
            "Idempotency Levels:",
            *[
                f"  {level}: {count}"
                for level, count in sorted(idempotency_counts.items())
            ],
            "=" * 60,
        ]

        # Print report (visible in pytest output with -v)
        print("\n".join(report))

        # Test always passes (informational only)
        assert True, "Registry statistics reported"
