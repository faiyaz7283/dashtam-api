# Documentation Templates

This directory contains standardized templates for all Dashtam documentation. Using these templates ensures consistency, completeness, and makes it easier for contributors to create high-quality documentation.

---

## 📚 Available Templates

| Template | Purpose | Use For |
|----------|---------|---------|
| [general-template.md](general-template.md) | Default template for all documentation | Any doc that doesn't fit other categories |
| [architecture-template.md](architecture-template.md) | System architecture and design docs | Design patterns, system architecture, technical decisions |
| [guide-template.md](guide-template.md) | Step-by-step how-to guides | Tutorials, setup guides, how-to documentation |
| [infrastructure-template.md](infrastructure-template.md) | Infrastructure and operations docs | Docker, CI/CD, database, deployment, monitoring |
| [implementation-template.md](implementation-template.md) | Implementation plans and roadmaps | Implementation plans, technical debt roadmaps, phased rollouts |
| [testing-template.md](testing-template.md) | Testing documentation | Test strategies, testing guides, QA documentation |
| [troubleshooting-template.md](troubleshooting-template.md) | Debugging and issue resolution docs | Bug investigations, root cause analysis, solutions |
| [research-template.md](research-template.md) | Research and ADR documents | Technical research, decision records, options analysis |
| [audit-template.md](audit-template.md) | Audit reports and compliance reviews | REST API audits, documentation audits, security audits, code quality reviews |
| [api-flow-template.md](api-flow-template.md) | API manual testing flows | User-centric API workflows for manual testing |
| [index-root-template.md](index-root-template.md) | Root documentation index | Root documentation entry point (docs/index.md only) |
| [index-section-template.md](index-section-template.md) | Section/directory index | Navigation/index pages for documentation sections |
| [readme-template.md](readme-template.md) | Feature/component READMEs | Feature documentation (env/README.md, tests/smoke/README.md) |
| [mermaid-diagram-standards.md](../development/guides/mermaid-diagram-standards.md) | **Diagram standards** | **REQUIRED: All diagrams MUST use Mermaid** |

---

## 🎯 Quick Start

### 1. Choose the Right Template

**Decision tree:**

- **Writing architecture docs?** → Use `architecture-template.md`
- **Writing how-to guide?** → Use `guide-template.md`
- **Documenting infrastructure?** → Use `infrastructure-template.md`
- **Writing implementation plan/roadmap?** → Use `implementation-template.md`
- **Writing test documentation?** → Use `testing-template.md`
- **Documenting a bug/issue resolution?** → Use `troubleshooting-template.md`
- **Researching options/decisions?** → Use `research-template.md`
- **Writing audit report/compliance review?** → Use `audit-template.md`
|- **Creating API flow?** → Use `api-flow-template.md`
|- **Creating root-level documentation index (docs/index.md only)?** → Use `index-root-template.md`
|- **Creating section/directory index?** → Use `index-section-template.md`
|- **Documenting a feature/component?** → Use `readme-template.md`
|- **Not sure?** → Use `general-template.md`

### 2. Copy the Template

```bash
# Copy template to your target location
cp docs/templates/guide-template.md docs/development/guides/my-new-guide.md
```

### 3. Fill Out the Template

Replace all placeholders:

- `[Bracketed text]` - Replace with your content
- `YYYY-MM-DD` - Replace with actual dates
- Keep the structure - Don't remove sections unless truly not applicable

### 4. Verify Quality

```bash
# Lint your new document
docker run --rm -v $(pwd):/workspace:ro -w /workspace node:24-alpine \
  npx markdownlint-cli2 "docs/path/to/your-new-doc.md"
```

---

## 📝 Template Structure

All templates follow this general structure:

1. **Title and Brief Description** - Clear, concise intro
2. **Horizontal Rule** - Visual separator
3. **Table of Contents** - For navigation (mandatory for comprehensive templates, optional for short docs)
4. **Main Content Sections** - Template-specific content
5. **References Section** - Links to related docs
6. **Horizontal Rule** - Separator before metadata
7. **Document Information** - Metadata at bottom (MkDocs-compatible)

### Table of Contents Guidelines

**When TOC is Mandatory:**

- Architecture documents (complex design docs)
- Infrastructure documents (operational guides)
- Implementation plans and roadmaps
- Testing strategy documents
- Documents > 200 lines

**When TOC is Optional:**

- General documents < 100 lines
- Simple how-to guides
- Short troubleshooting docs
- README files

**When to Add TOC to general-template:**

If your document using general-template exceeds ~150-200 lines or has multiple complex sections, add a TOC manually:

```markdown
## Table of Contents

- [Section 1](#section-1)
- [Section 2](#section-2)
- [Section 3](#section-3)
```

### Metadata Fields

All templates include standard metadata at the **bottom** of the document:

```markdown
---

## Document Information

**Template:** [link-to-template-file.md]
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD

```

**Important Changes (2025-10-19):**

- **"Template:" field (required)**: Replaced "Category" with "Template" to clearly link to the template file being used
- **Link to template**: The Template field must be a relative markdown link to the actual template file
- **Example**: `**Template:** [guide-template.md](../../templates/guide-template.md)`

**Why at the bottom?**

- Better readability for users (content first)
- MkDocs Material can extract and display metadata
- Keeps main content clean and focused

---

## ✅ Best Practices

### General Guidelines

1. **Be Concise** - Clear and direct language
2. **Use Examples** - Show, don't just tell
3. **Think User-First** - Write for your audience (end-users, developers, operators)
4. **Keep Updated** - Update Last Updated date when making changes
5. **Link Generously** - Reference related docs

### Writing Style

- ✅ Use active voice: "Run the command" not "The command should be run"
- ✅ Use present tense: "The system validates" not "The system will validate"
- ✅ Be specific: "Set timeout to 30 seconds" not "Set a reasonable timeout"
- ✅ Use code blocks: Always include language identifier (bash, python, yaml, etc.)
- ✅ Use lists: Break down complex information into bullets or numbered lists

### Markdown Quality

- ✅ Pass markdown linting (no MD warnings)
- ✅ Use proper heading hierarchy (# → ## → ### )
- ✅ Include alt text for images
- ✅ Use fenced code blocks with language tags
- ✅ No trailing spaces (use 0 or 2 for line breaks)

### Diagram Standards (REQUIRED)

- ✅ **MUST use Mermaid syntax** for diagrams (except directory trees)
- ✅ Directory trees → Use code blocks with tree structure (like `tree` command)
- ✅ Process flows → Use `flowchart TD`
- ✅ Database schemas → Use `erDiagram`
- ✅ API sequences → Use `sequenceDiagram`
- ❌ **NO image files** (PNG, JPG, SVG)
- ❌ **NO external tools** (draw.io, Lucidchart)
- 📖 **See:** [Mermaid Diagram Standards](../development/guides/mermaid-diagram-standards.md) for complete reference

---

## ✅ Document Structure Standards (CRITICAL)

**Updated:** 2025-10-19

All documentation files MUST follow these structural requirements:

### 1. Table of Contents (TOC) Requirements

#### Critical Rule: Each Template's TOC Defines Mandatory Top-Level Sections

The TOC in each template file defines the MANDATORY top-level sections that ALL documents using that template MUST have.

For example:

- All documents using `guide-template.md` MUST have: Overview, Prerequisites, Step-by-Step Instructions, Examples, Verification, Troubleshooting, Best Practices, Next Steps, References, Document Information
- All documents using `architecture-template.md` MUST have: Overview, Context, Architecture Goals, Design Decisions, Components, Implementation Details, Security Considerations, Performance Considerations, Testing Strategy, Future Enhancements, References, Document Information

**Document Requirements:**

- ✅ **ALL top-level sections from the template TOC MUST be present** in the document
- ✅ **Documents CAN add subsections** under the mandatory top-level sections
- ✅ **ALL subsections in the document MUST be listed in the document's TOC** with proper indentation (2 spaces)
- ✅ **"Document Information" MUST be the last item** in every TOC
- ✅ **TOC entries must match section headings exactly**

**What this means:**

- You CANNOT skip any top-level section from your template's TOC
- You CAN add subsections like "## Design Decisions" → "### Decision 1: Pattern Choice"
- You MUST list all these subsections in your document's TOC
- If a section doesn't apply, include it with "N/A" or "Not applicable" content

**Optional for short documents** (general template < 150 lines, README files, index files):

- TOC can be omitted if document is very short and simple
- When added, still follow all TOC requirements above

**Example Correct TOC:**

```markdown
## Table of Contents

- [Overview](#overview)
- [Section 1](#section-1)
  - [Subsection 1.1](#subsection-11)
  - [Subsection 1.2](#subsection-12)
- [Section 2](#section-2)
- [References](#references)
- [Document Information](#document-information)
```

### 2. Horizontal Divider Rules (EXACTLY 3)

Every document MUST have exactly **three horizontal dividers (`---`)**:

1. **First divider**: After title/description, ABOVE the TOC
2. **Second divider**: BELOW the TOC, before main content
3. **Third divider**: ABOVE "Document Information" section

**Example Structure:**

```markdown
# Document Title

Brief description.

---  <!-- Divider 1: Above TOC -->

## Table of Contents

- [Section 1](#section-1)
- [Document Information](#document-information)

---  <!-- Divider 2: Below TOC -->

## Section 1

Content here.

---  <!-- Divider 3: Above Document Information -->

## Document Information

**Template:** [template-name.md](link/to/template.md)
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD
```

### 3. Document Information Format (SIMPLIFIED)

All documents MUST use this simplified format:

```markdown
---

## Document Information

**Template:** [template-name.md](../../templates/template-name.md)
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD
```

**Required Fields:**

- **Template**: Relative markdown link to the template file (NOT "Category")
- **Created**: Document creation date (YYYY-MM-DD)
- **Last Updated**: Last modification date (YYYY-MM-DD)

**Template Link Examples by Directory:**

- `docs/api-flows/auth/` → `../../templates/api-flow-template.md`
- `docs/development/architecture/` → `../../templates/architecture-template.md`
- `docs/development/guides/` → `../../templates/guide-template.md`
- `docs/development/infrastructure/` → `../../templates/infrastructure-template.md`
- `docs/development/troubleshooting/` → `../../templates/troubleshooting-template.md`
- `docs/research/` → `../templates/research-template.md`
- `docs/reviews/` → `../templates/audit-template.md`
- `docs/testing/` → `../templates/testing-template.md`

**Migration of Extra Metadata:**

If existing documents have additional fields in Document Information:

- **"Status" field**: Remove (document location indicates status)
- **"API Version" field**: Keep for API flow documents only
- **"Environment" field**: Keep for infrastructure/troubleshooting docs only
- **Other fields**: Analyze and migrate to appropriate content sections or remove

### 4. Compliance Checklist

Before committing any documentation:

- [ ] **All mandatory top-level sections from template TOC are present** in the document
- [ ] **All subsections in document body are listed in document TOC** with proper indentation
- [ ] **"Document Information" is the last item** in TOC
- [ ] Document has exactly 3 horizontal dividers in correct positions
- [ ] Document Information uses "Template:" field with correct relative link to template
- [ ] Document Information has only required fields (Template, Created, Last Updated) plus template-specific optional fields
- [ ] All extra metadata migrated to content sections or removed
- [ ] Markdown linting passes: `make lint-md FILE="path/to/file.md"`
- [ ] Document structure matches the template file structure

---

## 📋 Metadata Standards

### Simplified Metadata (Updated 2025-10-19)

All templates now use simplified metadata **without the "Status" field**:

**Required Fields:**

- **Template**: Relative markdown link to the template file (e.g., `[guide-template.md](../../templates/guide-template.md)`)
- **Created**: Document creation date (YYYY-MM-DD)
- **Last Updated**: Last modification date (YYYY-MM-DD)

**Optional Fields** (template-specific):

- **Applies To**: Scope (Architecture template)
- **API Version**: API version (API Flow template)
- **Environment**: Target environment (Infrastructure, Troubleshooting templates)
- **Maintainer**: Responsible party (Index, README templates)
- And others as needed per template

**Why No Status Field?**

- Document location indicates status (active documentation only)
- Reduces maintenance overhead
- Simpler, cleaner metadata
- Outdated documents are updated or deleted, not archived
- Historical context belongs in architecture docs or git history

---

## 📂 Where to Put Your Documentation

Follow this directory structure:

```text
docs/
├── templates/              # You are here! (don't add content docs here)
├── api-flows/              # API manual testing flows
│   ├── auth/
│   └── providers/
├── development/            # Developer documentation
│   ├── architecture/       # System architecture and design
│   ├── guides/             # How-to guides and tutorials
│   ├── implementation/     # Implementation plans (active)
│   ├── infrastructure/     # Docker, CI/CD, deployment
│   └── troubleshooting/    # Bug investigations and resolutions
├── research/               # Research and ADRs (project-wide)
├── reviews/                # Code reviews, audits (project-wide)
└── testing/                # Testing strategy and guides (project-wide)
```

**Guidelines:**

- **Development docs** → `docs/development/[category]/`
- **Project-wide docs** → `docs/[category]/` (research, reviews, testing)
- **User-facing docs** → `docs/setup/`, `docs/api/`, or `docs/guides/` (future)
- **Troubleshooting/bug investigations** → `docs/development/troubleshooting/`

---

## 🎨 Customizing Templates

Templates are meant to be guides, not straitjackets:

**OK to customize:**

- ✅ Add sections specific to your topic
- ✅ Reorder sections if it improves flow
- ✅ Remove sections that truly don't apply (rarely needed)
- ✅ Expand placeholder text with more detailed guidance

**Don't remove:**

- ❌ Document Information section (metadata)
- ❌ Title and brief description
- ❌ Core sections central to the template's purpose

---

## 🔍 Examples

### Good Documentation

See these examples of well-structured docs:

- Architecture: `docs/development/architecture/jwt-authentication.md`
- Guide: `docs/development/guides/git-workflow.md`
- Infrastructure: `docs/development/infrastructure/docker-setup.md`
- Testing: `docs/testing/strategy.md`
- Research: `docs/research/authentication-approaches-research.md`
- Audit Report: `docs/reviews/REST_API_AUDIT_REPORT_2025-10-05.md`

### Template Usage Example

**Before (no template):**

```markdown
# My Feature

This is about my feature.

It does stuff.

## How to use

Run the command.
```

**After (using guide-template.md):**

Proper structure with:

- Clear title and description
- Organized sections (Overview, Prerequisites, Steps, etc.)
- Code blocks with commands
- Verification steps
- Troubleshooting
- Metadata at bottom:

  ```markdown
  ---
  
  ## Document Information
  
  **Template:** [guide-template.md](../../templates/guide-template.md)
  **Created:** 2025-10-13
  **Last Updated:** 2025-10-13
  ```

---

## 🚀 MkDocs Integration

These templates are designed to work seamlessly with MkDocs Material:

### Metadata Usage

The Document Information section at the bottom can be:

1. **Displayed in page footer** - MkDocs Material can extract and show metadata
2. **Used for sorting** - Sort docs by status, category, or date
3. **Used for search** - Filter docs by metadata fields
4. **Used for automation** - Generate doc indexes automatically

### Future Enhancements

When MkDocs is implemented, these templates will support:

- Automatic navigation generation
- Search by metadata fields
- Documentation versioning
- Multi-language support
- API documentation auto-generation

---

## 📋 Checklist for New Docs

When creating a new document:

- [ ] Choose appropriate template
- [ ] Copy template to correct location
- [ ] Replace all `[placeholder text]`
- [ ] Fill in metadata (Status, Created, Last Updated)
- [ ] Add examples and code samples
- [ ] Run markdown linting (`make lint-md`)
- [ ] Link from/to related documents
- [ ] Preview rendering (especially code blocks and tables)
- [ ] Commit with clear message

---

## 🆘 Need Help?

- **Questions about templates?** Check existing docs for examples
- **Not sure which template?** Start with `general-template.md`
- **Template missing something?** Propose improvements in PR
- **Documentation standards?** See WARP.md section on documentation

---

## 🔄 Maintaining Templates

### When to Update Templates

- New best practices emerge
- MkDocs features require metadata changes
- Consistent patterns identified across docs
- User feedback suggests improvements

### How to Propose Changes

1. Create feature branch
2. Update template(s) with clear rationale
3. Update this README if needed
4. Create PR with examples showing improvements
5. Get review and merge

---

## Document Information

**Status:** Active
**Category:** Documentation Standards
**Created:** 2025-10-13
**Last Updated:** 2025-10-13
**Purpose:** Central guide for all documentation templates in Dashtam project
