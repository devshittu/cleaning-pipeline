# CLI Documentation Enhancement Guide

## 🎉 New Features

The CLI now includes **auto-generated documentation** that mirrors the OpenAPI documentation style used by the API. This provides a unified documentation experience across both CLI and API interfaces.

---

## 📚 New Documentation Commands

### 1. `docs show` - View Documentation in Terminal

Display comprehensive CLI documentation directly in your terminal with beautiful Markdown formatting.

**Docker:**

```bash
docker compose exec ingestion-service python -m src.main_cli docs show
```

**Non-Docker:**

```bash
python -m src.main_cli docs show
```

**Output:**

- Full command reference
- Parameter descriptions
- Usage examples
- Type information
- Default values

---

### 2. `docs export` - Export Documentation

Export CLI documentation in multiple formats for integration with other tools or publishing.

#### Export as Markdown

**Docker:**

```bash
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format markdown \
  -o /app/data/CLI_REFERENCE.md
```

**Non-Docker:**

```bash
python -m src.main_cli docs export --format markdown -o CLI_REFERENCE.md
```

**Output File Structure:**

```markdown
# Data Ingestion & Preprocessing CLI

**Version:** 1.0.0

A command-line interface for cleaning and preprocessing news articles...

## Commands

### `process`

Process a JSONL file containing news articles.

**Usage:** `ingestion-cli process [OPTIONS]`

**Options:**

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `-i, --input` | Path | True | None | Path to input JSONL file |
| `-o, --output` | Path | True | None | Path to output JSONL file |
| `--celery/--no-celery` | BOOL | False | False | Submit to Celery workers |
...

**Examples:**

- Process locally (synchronous)
  ```bash
  ingestion-cli process -i input.jsonl -o output.jsonl
  ```

```

#### Export as JSON

**Docker:**
```bash
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format json \
  -o /app/data/cli-schema.json
```

**Output:**

```json
{
  "metadata": {
    "title": "Data Ingestion & Preprocessing CLI",
    "version": "1.0.0",
    "description": "A command-line interface for cleaning and preprocessing news articles...",
    "contact": {
      "name": "Support",
      "email": "support@example.com"
    }
  },
  "commands": {
    "process": {
      "name": "process",
      "description": "Process a JSONL file containing news articles.",
      "usage": "ingestion-cli process [OPTIONS]",
      "options": [
        {
          "name": "input_path",
          "type": "Path",
          "required": true,
          "default": "None",
          "flags": ["-i", "--input"],
          "help": "Path to input JSONL file"
        }
      ],
      "examples": [...]
    }
  }
}
```

#### Export as HTML

**Docker:**

```bash
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format html \
  -o /app/data/cli-docs.html
```

**Result:** Beautiful, styled HTML documentation that can be:

- Hosted on a web server
- Included in internal wikis
- Distributed to team members
- Embedded in documentation sites

---

### 3. `docs openapi` - OpenAPI-Style Schema

Generate an OpenAPI-compatible JSON schema for CLI commands. This enables:

- Automated client generation
- Integration with API documentation tools
- Consistent schema across CLI and API
- Type-safe client libraries

**Docker:**

```bash
docker compose exec ingestion-service python -m src.main_cli docs openapi \
  -o /app/data/cli-openapi.json
```

**Output:**

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "Data Ingestion & Preprocessing CLI",
    "version": "1.0.0",
    "description": "A command-line interface for cleaning and preprocessing news articles...",
    "contact": {
      "name": "Support",
      "email": "support@example.com",
      "url": "https://github.com/your-repo"
    }
  },
  "commands": {
    "process": {
      "summary": "Process a JSONL file containing news articles.",
      "operationId": "cli_process",
      "parameters": [
        {
          "name": "input_path",
          "in": "cli",
          "required": true,
          "schema": {
            "type": "string",
            "default": null
          },
          "description": "Path to input JSONL file",
          "flags": ["-i", "--input"]
        },
        {
          "name": "output_path",
          "in": "cli",
          "required": true,
          "schema": {
            "type": "string",
            "default": null
          },
          "description": "Path to output JSONL file",
          "flags": ["-o", "--output"]
        }
      ]
    }
  }
}
```

---

## 🔗 Integration with API Documentation

### Unified Documentation Approach

Both CLI and API now share similar documentation structures:

| Feature | CLI | API |
|---------|-----|-----|
| **Format** | OpenAPI-style JSON/Markdown | OpenAPI 3.1.0 |
| **Interactive Docs** | Terminal (Rich) | Swagger UI |
| **Export Formats** | JSON, Markdown, HTML | JSON (OpenAPI spec) |
| **Versioning** | ✅ 1.0.0 | ✅ v1 |
| **Examples** | ✅ Command examples | ✅ cURL/Python/JS |
| **Parameter Docs** | ✅ Full descriptions | ✅ Full descriptions |
| **Type Safety** | ✅ JSON Schema types | ✅ Pydantic models |

### Cross-Reference Example

**API Documentation (Swagger):**

```
POST /v1/preprocess
Process a single article synchronously
```

**CLI Documentation (Markdown):**

```
process
Process a JSONL file containing news articles
```

Both provide the same functionality with consistent parameter descriptions.

---

## 📖 Enhanced Help System

### Improved Command Help

All commands now have rich, detailed help text with examples.

**View Main Help:**

```bash
docker compose exec ingestion-service python -m src.main_cli --help
```

**Output:**

```
🧹 Data Ingestion & Preprocessing CLI

A command-line interface for cleaning and preprocessing news articles.
Supports batch processing, Celery integration, and multiple storage backends.

Quick Start:
    ingestion-cli info                    # Show system information
    ingestion-cli test-model              # Test spaCy model
    ingestion-cli validate input.jsonl    # Validate file
    ingestion-cli process -i in.jsonl -o out.jsonl  # Process articles

Documentation:
    ingestion-cli docs export --format markdown  # Export CLI docs
    ingestion-cli docs show                      # View docs in terminal

For detailed help on any command, use:
    ingestion-cli COMMAND --help

Commands:
  docs         📚 Documentation commands for CLI reference and export.
  info         Display system and configuration information.
  process      Process a JSONL file containing news articles.
  test-model   Test the spaCy model with sample text.
  validate     Validate a JSONL file for correct format and schema.
```

**Command-Specific Help:**

```bash
docker compose exec ingestion-service python -m src.main_cli process --help
```

---

## 🎯 Use Cases

### 1. Team Onboarding

Generate HTML documentation for new team members:

```bash
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format html \
  -o /app/data/onboarding-cli-guide.html

# Host on internal wiki or email to new team members
```

### 2. CI/CD Pipeline Documentation

Generate JSON schema for automated testing:

```bash
docker compose exec ingestion-service python -m src.main_cli docs openapi \
  -o cli-schema.json

# Use in CI/CD to validate CLI commands
# Generate type-safe wrappers
```

### 3. External Documentation Sites

Export Markdown for documentation generators (MkDocs, Sphinx, etc.):

```bash
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format markdown \
  -o docs/cli-reference.md

# Commit to repository
# Auto-publish to docs site
```

### 4. Integration with API Documentation

Compare CLI and API capabilities:

```bash
# Export CLI schema
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format json \
  -o cli-schema.json

# Get API schema
curl http://localhost:8000/openapi.json > api-schema.json

# Compare or merge for unified documentation
```

### 5. Terminal Quick Reference

View documentation without leaving terminal:

```bash
docker compose exec ingestion-service python -m src.main_cli docs show | less
```

---

## 🔄 Documentation Generation Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Commands (Click)                      │
│  - Decorators with help text                                │
│  - Type hints                                                │
│  - Parameter descriptions                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         Documentation Generator                              │
│  generate_cli_documentation(ctx, output_format)             │
│  - Introspects Click commands                               │
│  - Extracts metadata                                         │
│  - Builds structured schema                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┬──────────────┐
         │           │           │              │
         ▼           ▼           ▼              ▼
    ┌────────┐  ┌────────┐  ┌────────┐    ┌──────────┐
    │ JSON   │  │Markdown│  │  HTML  │    │ OpenAPI  │
    │ Schema │  │  Docs  │  │  Docs  │    │  Schema  │
    └────────┘  └────────┘  └────────┘    └──────────┘
         │           │           │              │
         └───────────┴───────────┴──────────────┘
                     │
                     ▼
         ┌───────────────────────────┐
         │  Documentation Outputs     │
         │  - Files                   │
         │  - Terminal display        │
         │  - Integration tools       │
         └───────────────────────────┘
```

---

## 📊 Documentation Metadata

The CLI now includes rich metadata similar to OpenAPI specs:

```python
CLI_METADATA = {
    "title": "Data Ingestion & Preprocessing CLI",
    "version": "1.0.0",
    "description": "A command-line interface for cleaning and preprocessing news articles with NLP enrichment.",
    "author": "Data Engineering Team",
    "contact": {
        "name": "Support",
        "email": "support@example.com",
        "url": "https://github.com/your-repo"
    }
}
```

**Customize** by editing this section in `src/main_cli.py`.

---

## 🔍 Example: Complete Documentation Workflow

### Step 1: Generate All Documentation Formats

```bash
# Create docs directory
mkdir -p docs/cli

# Export Markdown (for MkDocs/Sphinx)
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format markdown \
  -o /app/data/cli-reference.md

# Export HTML (for internal wiki)
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format html \
  -o /app/data/cli-reference.html

# Export JSON (for tooling)
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format json \
  -o /app/data/cli-schema.json

# Export OpenAPI schema (for integration)
docker compose exec ingestion-service python -m src.main_cli docs openapi \
  -o /app/data/cli-openapi.json
```

### Step 2: Copy to Documentation Directory

```bash
# Copy from Docker container to host
docker compose cp ingestion-service:/app/data/cli-reference.md ./docs/cli/
docker compose cp ingestion-service:/app/data/cli-reference.html ./docs/cli/
docker compose cp ingestion-service:/app/data/cli-schema.json ./docs/cli/
docker compose cp ingestion-service:/app/data/cli-openapi.json ./docs/cli/
```

### Step 3: Commit to Repository

```bash
git add docs/cli/
git commit -m "docs: update CLI reference documentation"
git push
```

### Step 4: Auto-Deploy

Your CI/CD pipeline automatically:

- Publishes Markdown to docs site
- Hosts HTML on internal wiki
- Uses JSON schema for client generation
- Validates CLI commands in tests

---

## 🎨 Customization

### Add Command Examples

Edit the documentation generator in `src/main_cli.py`:

```python
# Add command-specific examples
if cmd_name == "process":
    cmd_docs["examples"] = [
        {
            "description": "Process file locally (synchronous)",
            "command": "ingestion-cli process -i input.jsonl -o output.jsonl"
        },
        {
            "description": "Process with Celery (asynchronous)",
            "command": "ingestion-cli process -i input.jsonl -o output.jsonl --celery"
        }
    ]
```

### Customize Metadata

Update contact information and branding:

```python
CLI_METADATA = {
    "title": "Your Custom CLI Name",
    "version": "2.0.0",
    "description": "Your custom description",
    "author": "Your Team",
    "contact": {
        "name": "Your Support Team",
        "email": "support@yourcompany.com",
        "url": "https://github.com/yourorg/yourrepo"
    }
}
```

### Add Custom Export Formats

Extend the documentation generator:

```python
def _format_rst_docs(docs):
    """Format documentation as ReStructuredText for Sphinx."""
    rst = f".. _{docs['metadata']['title']}:\n\n"
    rst += f"{docs['metadata']['title']}\n"
    rst += "=" * len(docs['metadata']['title']) + "\n\n"
    # ... add formatting logic
    return rst
```

---

## 🚀 Advanced Features

### 1. Type Mapping

CLI parameter types are automatically mapped to JSON Schema types:

```python
def _map_click_type_to_json_type(click_type):
    type_mapping = {
        'STRING': 'string',
        'INT': 'integer',
        'FLOAT': 'number',
        'BOOL': 'boolean',
        'Path': 'string',
        'Choice': 'string'
    }
    return type_mapping.get(type_name, 'string')
```

### 2. Rich Terminal Display

Documentation uses Rich library for beautiful terminal output:

- Markdown rendering
- Tables
- Syntax highlighting
- Progress bars

### 3. Introspection

Documentation is generated via Click context introspection:

- No manual documentation maintenance
- Always in sync with actual CLI
- Parameter descriptions from docstrings
- Type information from decorators

---

## 📝 Summary of Changes

### What Was Added

✅ **New `docs` command group** with 3 subcommands:

- `docs show` - Terminal display
- `docs export` - Export to file (Markdown/JSON/HTML)
- `docs openapi` - OpenAPI-style schema

✅ **Auto-generated documentation** from CLI code:

- Command descriptions
- Parameter types and defaults
- Required/optional flags
- Usage examples

✅ **Multiple export formats**:

- Markdown (for MkDocs, Sphinx, GitHub)
- JSON (for tooling, integration)
- HTML (for wikis, websites)
- OpenAPI JSON (for API parity)

✅ **Rich metadata**:

- Version information
- Contact details
- Descriptions
- Examples per command

### What Wasn't Changed

✅ **No functional changes** to existing commands:

- `process`, `validate`, `test-model`, `info` work identically
- All parameters and options unchanged
- Processing logic untouched
- Backward compatible

✅ **No configuration changes** required
✅ **No breaking changes**
✅ **No regressions introduced**

---

## 🎯 Next Steps

### For Developers

1. **Export documentation** after each release:

   ```bash
   docker compose exec ingestion-service python -m src.main_cli docs export \
     --format markdown -o CHANGELOG.md
   ```

2. **Integrate with CI/CD**:

   ```yaml
   # .github/workflows/docs.yml
   - name: Generate CLI docs
     run: |
       docker compose exec ingestion-service python -m src.main_cli docs export \
         --format markdown -o docs/cli-reference.md
       git add docs/cli-reference.md
   ```

3. **Create unified docs site** combining API and CLI documentation

### For Users

1. **Quick reference in terminal**:

   ```bash
   docker compose exec ingestion-service python -m src.main_cli docs show | less
   ```

2. **Download offline documentation**:

   ```bash
   docker compose exec ingestion-service python -m src.main_cli docs export \
     --format html -o /app/data/cli-guide.html
   ```

3. **Share with team**:

   ```bash
   # Export and email
   docker compose exec ingestion-service python -m src.main_cli docs export \
     --format markdown -o /app/data/CLI_GUIDE.md
   ```

---

## 🔗 Related Documentation

- **[API Usage Guide](./API_USAGE.md)** - REST API documentation
- **[CLI Usage Guide](./CLI_USAGE.md)** - CLI usage examples
- **[README.md](./README.md)** - General project documentation
- **[API OpenAPI Spec](http://localhost:8000/docs)** - Interactive API docs

---

**Questions?** Run `docker compose exec ingestion-service python -m src.main_cli --help`



---
---
---
---

# Testing New Documentation Features

## ✅ Verification Checklist

Run these commands to verify all features work without regressions.

---

## 1. Test Existing Commands (No Regressions)

### Test `info` Command

```bash
docker compose exec ingestion-service python -m src.main_cli info
```

**Expected:** ✅ Displays system information table

---

### Test `test-model` Command

```bash
docker compose exec ingestion-service python -m src.main_cli test-model \
  --text "Apple Inc. announced products in San Francisco yesterday."
```

**Expected:** ✅ Shows original text, cleaned text, and 3 entities in table format (NOT duplicated columns)

---

### Test `validate` Command

```bash
docker compose exec ingestion-service python -m src.main_cli validate \
  /app/data/valid_test.jsonl
```

**Expected:** ✅ Shows validation results with 0 errors

---

### Test `process` Command (Sync)

```bash
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/valid_test.jsonl \
  -o /app/data/test_output.jsonl
```

**Expected:** ✅ Processes successfully, no error about `custom_cleaning_config`

---

### Test `process` with Custom Config Flags

```bash
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/valid_test.jsonl \
  -o /app/data/test_output_no_typo.jsonl \
  --disable-typo-correction
```

**Expected:** ✅ Processes with custom config applied

---

## 2. Test New Documentation Commands

### Test `docs show`

```bash
docker compose exec ingestion-service python -m src.main_cli docs show
```

**Expected:** ✅ Displays formatted Markdown documentation in terminal

**Verify:**

- Shows CLI title and version
- Lists all commands
- Shows parameter tables
- Includes examples

---

### Test `docs export` - Markdown

```bash
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format markdown \
  -o /app/data/cli-docs.md

# Verify file created
docker compose exec ingestion-service cat /app/data/cli-docs.md | head -20
```

**Expected:** ✅ Creates Markdown file with complete documentation

**Verify File Contains:**

- `# Data Ingestion & Preprocessing CLI`
- Command sections with `###` headers
- Parameter tables
- Examples

---

### Test `docs export` - JSON

```bash
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format json \
  -o /app/data/cli-docs.json

# Verify JSON structure
docker compose exec ingestion-service python -c "
import json
with open('/app/data/cli-docs.json') as f:
    data = json.load(f)
    print('Commands:', list(data['commands'].keys()))
    print('Metadata:', data['metadata']['title'])
"
```

**Expected:** ✅ Creates valid JSON with complete schema

**Verify:**

- Valid JSON syntax
- Contains `metadata` and `commands` keys
- Each command has `name`, `description`, `options`, `examples`

---

### Test `docs export` - HTML

```bash
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format html \
  -o /app/data/cli-docs.html

# Copy to host to view in browser
docker compose cp ingestion-service:/app/data/cli-docs.html ./cli-docs.html

# Open in browser
open cli-docs.html  # macOS
# or
xdg-open cli-docs.html  # Linux
# or
start cli-docs.html  # Windows
```

**Expected:** ✅ Creates styled HTML page

**Verify in Browser:**

- Proper HTML structure
- CSS styling applied
- Tables render correctly
- Code blocks formatted
- All commands listed

---

### Test `docs openapi`

```bash
docker compose exec ingestion-service python -m src.main_cli docs openapi \
  -o /app/data/cli-openapi.json

# Verify OpenAPI structure
docker compose exec ingestion-service python -c "
import json
with open('/app/data/cli-openapi.json') as f:
    data = json.load(f)
    print('OpenAPI Version:', data['openapi'])
    print('Title:', data['info']['title'])
    print('Commands:', list(data['commands'].keys()))
"
```

**Expected:** ✅ Creates OpenAPI 3.1.0 compatible schema

**Verify:**

- `openapi: "3.1.0"`
- `info` section with title, version, contact
- `commands` with proper parameter schemas

---

## 3. Test Help System

### Main Help

```bash
docker compose exec ingestion-service python -m src.main_cli --help
```

**Expected:** ✅ Shows enhanced help with:

- ASCII art or emoji icons
- Quick start section
- Documentation section mentioning new `docs` commands
- All command listings including `docs`

---

### Docs Group Help

```bash
docker compose exec ingestion-service python -m src.main_cli docs --help
```

**Expected:** ✅ Shows:

- `show` command
- `export` command
- `openapi` command
- Brief descriptions

---

### Export Command Help

```bash
docker compose exec ingestion-service python -m src.main_cli docs export --help
```

**Expected:** ✅ Shows:

- `--format` option with choices (markdown, json, html)
- `-o, --output` option
- Examples section

---

## 4. Integration Tests

### Test Documentation Matches Actual Commands

```bash
# Export docs
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format json \
  -o /app/data/cli-schema.json

# Verify 'process' command has correct parameters
docker compose exec ingestion-service python -c "
import json
with open('/app/data/cli-schema.json') as f:
    data = json.load(f)
    process_cmd = data['commands']['process']
    
    # Check required options exist
    options = {opt['name']: opt for opt in process_cmd['options']}
    
    assert 'input_path' in options, 'Missing input_path'
    assert 'output_path' in options, 'Missing output_path'
    assert 'celery' in options, 'Missing celery flag'
    assert 'disable_typo_correction' in options, 'Missing disable_typo_correction'
    
    print('✅ All expected parameters present in docs')
"
```

**Expected:** ✅ No assertion errors, all parameters documented

---

### Compare with API OpenAPI Spec

```bash
# Get API spec
curl -s http://localhost:8000/openapi.json > api-openapi.json

# Get CLI spec
docker compose exec ingestion-service python -m src.main_cli docs openapi \
  -o /app/data/cli-openapi.json
docker compose cp ingestion-service:/app/data/cli-openapi.json ./

# Compare structure
python -c "
import json

with open('api-openapi.json') as f:
    api_spec = json.load(f)

with open('cli-openapi.json') as f:
    cli_spec = json.load(f)

print('API OpenAPI version:', api_spec.get('openapi'))
print('CLI OpenAPI version:', cli_spec.get('openapi'))
print('Both use OpenAPI 3.1.0:', 
      api_spec.get('openapi') == cli_spec.get('openapi') == '3.1.0')
"
```

**Expected:** ✅ Both use OpenAPI 3.1.0 format

---

## 5. Performance Tests

### Documentation Generation Speed

```bash
time docker compose exec ingestion-service python -m src.main_cli docs show > /dev/null
```

**Expected:** ✅ Completes in < 2 seconds

---

### Export Performance

```bash
time docker compose exec ingestion-service python -m src.main_cli docs export \
  --format markdown \
  -o /app/data/perf-test.md
```

**Expected:** ✅ Completes in < 1 second

---

## 6. Edge Cases

### Test Export Without Output Path (Print to stdout)

```bash
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format markdown | head -20
```

**Expected:** ✅ Prints to terminal instead of file

---

### Test Invalid Format

```bash
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format xml
```

**Expected:** ❌ Shows error: "Invalid value for '--format': 'xml' is not one of 'markdown', 'json', 'html'"

---

### Test Long Text in Terminal

```bash
docker compose exec ingestion-service python -m src.main_cli docs show | wc -l
```

**Expected:** ✅ Shows line count (should be > 100 lines)

---

## 7. Regression Tests

### Verify Original Functionality Still Works

```bash
# Create test input
cat > /tmp/regression_test.jsonl << 'EOF'
{"document_id":"reg-001","text":"This is a test with typos like teh and appel in San Francisco."}
{"document_id":"reg-002","text":"The price is $100 and it weighs 5kg in New York."}
EOF

# Copy to container
docker compose cp /tmp/regression_test.jsonl ingestion-service:/app/data/

# Process normally
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/regression_test.jsonl \
  -o /app/data/regression_output.jsonl

# Verify output
docker compose exec ingestion-service python -c "
import json

with open('/app/data/regression_output.jsonl') as f:
    for line in f:
        data = json.loads(line)
        cleaned = data['processed_data']['cleaned_text']
        print(f'Doc {data[\"document_id\"]}: {cleaned}')
        
        # Verify typos corrected
        if data['document_id'] == 'reg-001':
            assert 'the' in cleaned.lower(), 'Typo correction failed'
            assert 'apple' in cleaned.lower(), 'Typo correction failed'
            assert 'San Francisco' in cleaned, 'NER protection failed'
            print('✅ Typo correction and NER protection working')
        
        # Verify currency standardization
        if data['document_id'] == 'reg-002':
            assert 'USD 100' in cleaned, 'Currency standardization failed'
            assert '5 kilograms' in cleaned, 'Unit standardization failed'
            print('✅ Currency and unit standardization working')
"
```

**Expected:** ✅ All assertions pass, no regressions

---

## 8. Documentation Quality Tests

### Check for Required Sections

```bash
docker compose exec ingestion-service python -c "
import json

with open('/app/data/cli-schema.json') as f:
    data = json.load(f)

# Check metadata
assert 'metadata' in data
assert 'title' in data['metadata']
assert 'version' in data['metadata']
assert 'description' in data['metadata']
assert 'contact' in data['metadata']

# Check commands
assert 'commands' in data
assert len(data['commands']) >= 5  # process, validate, test-model, info, docs

# Check each command has required fields
for cmd_name, cmd_data in data['commands'].items():
    assert 'name' in cmd_data, f'{cmd_name} missing name'
    assert 'description' in cmd_data, f'{cmd_name} missing description'
    assert 'options' in cmd_data, f'{cmd_name} missing options'
    
    # Check each option has required fields
    for opt in cmd_data['options']:
        assert 'name' in opt, f'Option in {cmd_name} missing name'
        assert 'type' in opt, f'Option in {cmd_name} missing type'
        assert 'help' in opt, f'Option in {cmd_name} missing help'

print('✅ All documentation sections present and valid')
"
```

**Expected:** ✅ All assertions pass

---

## 9. Final Verification

### Complete Test Suite

```bash
#!/bin/bash
echo "🧪 Running Complete CLI Documentation Test Suite"
echo "================================================"

# Test 1: Existing commands work
echo ""
echo "Test 1: Existing Commands (No Regressions)"
docker compose exec ingestion-service python -m src.main_cli info > /dev/null && echo "✅ info command works" || echo "❌ info command failed"
docker compose exec ingestion-service python -m src.main_cli test-model --text "Test" > /dev/null && echo "✅ test-model command works" || echo "❌ test-model command failed"

# Test 2: New docs commands work
echo ""
echo "Test 2: New Documentation Commands"
docker compose exec ingestion-service python -m src.main_cli docs show > /dev/null && echo "✅ docs show works" || echo "❌ docs show failed"
docker compose exec ingestion-service python -m src.main_cli docs export --format markdown -o /app/data/test.md > /dev/null && echo "✅ docs export markdown works" || echo "❌ docs export markdown failed"
docker compose exec ingestion-service python -m src.main_cli docs export --format json -o /app/data/test.json > /dev/null && echo "✅ docs export json works" || echo "❌ docs export json failed"
docker compose exec ingestion-service python -m src.main_cli docs export --format html -o /app/data/test.html > /dev/null && echo "✅ docs export html works" || echo "❌ docs export html failed"
docker compose exec ingestion-service python -m src.main_cli docs openapi -o /app/data/test-openapi.json > /dev/null && echo "✅ docs openapi works" || echo "❌ docs openapi failed"

# Test 3: Files were created
echo ""
echo "Test 3: Output Files Created"
docker compose exec ingestion-service test -f /app/data/test.md && echo "✅ Markdown file created" || echo "❌ Markdown file missing"
docker compose exec ingestion-service test -f /app/data/test.json && echo "✅ JSON file created" || echo "❌ JSON file missing"
docker compose exec ingestion-service test -f /app/data/test.html && echo "✅ HTML file created" || echo "❌ HTML file missing"
docker compose exec ingestion-service test -f /app/data/test-openapi.json && echo "✅ OpenAPI file created" || echo "❌ OpenAPI file missing"

# Test 4: JSON files are valid
echo ""
echo "Test 4: JSON Schema Validation"
docker compose exec ingestion-service python -c "import json; json.load(open('/app/data/test.json'))" && echo "✅ CLI JSON is valid" || echo "❌ CLI JSON invalid"
docker compose exec ingestion-service python -c "import json; json.load(open('/app/data/test-openapi.json'))" && echo "✅ OpenAPI JSON is valid" || echo "❌ OpenAPI JSON invalid"

# Test 5: Custom config still works
echo ""
echo "Test 5: Custom Config (No Regression)"
docker compose exec ingestion-service python -m src.main_cli process \
  -i /app/data/valid_test.jsonl \
  -o /app/data/test_custom.jsonl \
  --disable-typo-correction > /dev/null 2>&1 && echo "✅ Custom config works" || echo "❌ Custom config failed"

echo ""
echo "================================================"
echo "✨ Test Suite Complete!"
echo ""
```

**Save this as `test-cli-docs.sh` and run:**

```bash
chmod +x test-cli-docs.sh
./test-cli-docs.sh
```

---

## 10. Visual Verification

### Open Documentation in Browser

```bash
# Generate HTML docs
docker compose exec ingestion-service python -m src.main_cli docs export \
  --format html \
  -o /app/data/cli-documentation.html

# Copy to host
docker compose cp ingestion-service:/app/data/cli-documentation.html ./

# Open in browser
open cli-documentation.html  # macOS
# or navigate to file in your browser
```

**Verify in Browser:**

- [ ] Page loads without errors
- [ ] CSS styling is applied
- [ ] All commands are listed
- [ ] Tables render correctly
- [ ] Code blocks are formatted
- [ ] Links (if any) work
- [ ] Responsive on mobile

---

## 11. Side-by-Side Comparison

### Compare API vs CLI Documentation

```bash
# Generate both
curl -s http://localhost:8000/openapi.json | jq . > api-spec.json

docker compose exec ingestion-service python -m src.main_cli docs openapi \
  -o /app/data/cli-spec.json
docker compose cp ingestion-service:/app/data/cli-spec.json ./

# Compare structure
python3 << 'EOF'
import json

with open('api-spec.json') as f:
    api = json.load(f)
    
with open('cli-spec.json') as f:
    cli = json.load(f)

print("API Documentation:")
print(f"  Title: {api['info']['title']}")
print(f"  Version: {api['info']['version']}")
print(f"  Endpoints: {len(api.get('paths', {}))}")

print("\nCLI Documentation:")
print(f"  Title: {cli['info']['title']}")
print(f"  Version: {cli['info']['version']}")
print(f"  Commands: {len(cli.get('commands', {}))}")

print("\nBoth use OpenAPI 3.1.0:", api['openapi'] == cli['openapi'] == '3.1.0')
print("Both have contact info:", 'contact' in api['info'] and 'contact' in cli['info'])
print("Both have descriptions:", 'description' in api['info'] and 'description' in cli['info'])
EOF
```

**Expected Output:**

```
API Documentation:
  Title: Data Ingestion & Preprocessing Service
  Version: 1.0.0
  Endpoints: 5

CLI Documentation:
  Title: Data Ingestion & Preprocessing CLI
  Version: 1.0.0
  Commands: 5

Both use OpenAPI 3.1.0: True
Both have contact info: True
Both have descriptions: True
```

---

## 12. Documentation Coverage Test

### Ensure All Commands Are Documented

```bash
docker compose exec ingestion-service python << 'EOF'
import json
from click.testing import CliRunner
from src.main_cli import cli

# Get all CLI commands
runner = CliRunner()
result = runner.invoke(cli, ['--help'])
cli_commands_from_help = set()

# Parse help output to extract command names
for line in result.output.split('\n'):
    if line.strip() and not line.startswith(' ') and not line.startswith('Commands:'):
        parts = line.strip().split()
        if len(parts) > 0 and parts[0].isalpha():
            cli_commands_from_help.add(parts[0])

# Get documented commands
with open('/app/data/test.json') as f:
    docs = json.load(f)
    documented_commands = set(docs['commands'].keys())

print(f"Commands in CLI: {cli_commands_from_help}")
print(f"Commands in docs: {documented_commands}")

# Verify all commands are documented
missing = cli_commands_from_help - documented_commands
extra = documented_commands - cli_commands_from_help

if missing:
    print(f"❌ Missing from docs: {missing}")
else:
    print("✅ All commands are documented")

if extra:
    print(f"⚠️  Extra in docs: {extra}")
EOF
```

**Expected:** ✅ All commands are documented, no missing entries

---

## 13. Performance Benchmark

### Measure Documentation Generation Speed

```bash
# Benchmark 10 runs
for i in {1..10}; do
    /usr/bin/time -f "%E" docker compose exec ingestion-service python -m src.main_cli docs export \
      --format markdown \
      -o /app/data/benchmark-$i.md 2>&1 | grep -E "^[0-9]"
done | awk '{ sum += $1; count++ } END { print "Average:", sum/count, "seconds" }'
```

**Expected:** ✅ Average < 2 seconds per generation

---

## 14. Memory Usage Test

### Check Memory Footprint

```bash
# Monitor memory during doc generation
docker stats ingestion-service --no-stream &
STATS_PID=$!

docker compose exec ingestion-service python -m src.main_cli docs export \
  --format html \
  -o /app/data/memory-test.html

kill $STATS_PID
```

**Expected:** ✅ Memory usage stays reasonable (< 1GB increase)

---

## 15. Cleanup

### Remove Test Files

```bash
docker compose exec ingestion-service sh -c "rm -f /app/data/test*.* /app/data/benchmark-*"
```

---

## Summary Checklist

After running all tests, verify:

### Core Functionality (No Regressions)

- [ ] `info` command works
- [ ] `test-model` command works (with fixed entity table)
- [ ] `validate` command works
- [ ] `process` command works (sync mode)
- [ ] `process` command works (Celery mode)
- [ ] Custom config flags work (`--disable-typo-correction`, etc.)

### New Documentation Features

- [ ] `docs show` displays in terminal
- [ ] `docs export --format markdown` creates valid Markdown
- [ ] `docs export --format json` creates valid JSON
- [ ] `docs export --format html` creates styled HTML
- [ ] `docs openapi` creates OpenAPI 3.1.0 schema
- [ ] Documentation output can be written to files
- [ ] Documentation can print to stdout

### Quality Checks

- [ ] All commands are documented
- [ ] All parameters are documented
- [ ] Examples are included for each command
- [ ] JSON schemas are valid
- [ ] HTML renders correctly in browser
- [ ] Performance is acceptable (< 2s generation)
- [ ] Memory usage is reasonable

### Integration

- [ ] CLI docs structure mirrors API docs structure
- [ ] Both use OpenAPI-compatible schemas
- [ ] Metadata is consistent across formats
- [ ] Contact information is present

---

## Troubleshooting

### Issue: "Command 'docs' not found"

**Solution:**

```bash
# Rebuild the container
docker compose down
docker compose build ingestion-service
docker compose up -d
```

### Issue: JSON export fails

**Solution:**

```bash
# Check Python JSON module
docker compose exec ingestion-service python -c "import json; print('JSON OK')"

# Check file permissions
docker compose exec ingestion-service ls -la /app/data/
```

### Issue: HTML doesn't render properly

**Solution:**

- Check browser console for errors
- Verify complete HTML structure in file
- Test in different browser

### Issue: Documentation is empty

**Solution:**

```bash
# Verify CLI has commands
docker compose exec ingestion-service python -m src.main_cli --help

# Check Click context
docker compose exec ingestion-service python << 'EOF'
from src.main_cli import cli
print(f"Commands: {list(cli.commands.keys())}")
EOF
```

---

## Success Criteria

All tests pass when:

1. ✅ **No regressions**: All existing commands work identically
2. ✅ **New features work**: All `docs` commands execute successfully
3. ✅ **Valid output**: All export formats are valid and complete
4. ✅ **Complete coverage**: All CLI commands are documented
5. ✅ **Performance**: Documentation generates in < 2 seconds
6. ✅ **Quality**: HTML renders properly, JSON validates, Markdown formats correctly

---

**Next Step:** If all tests pass, the enhancement is ready for production! 🎉
