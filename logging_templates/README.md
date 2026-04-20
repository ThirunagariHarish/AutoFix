# Logging Templates

This directory contains **language-specific logging framework snippets** that the
Claude Code agent uses when injecting standardised structured logging into a monitored
project during Phase 1 (logging standardisation).

Each file is a **ready-to-use reference snippet** the agent reads, adapts to the
project structure, and places at the appropriate path inside the target repo.

---

## Templates

| File | Language | Framework | Install command |
|------|----------|-----------|-----------------|
| `python_structlog.py` | Python | [structlog](https://www.structlog.org/) | `pip install structlog>=23.0.0` |
| `python_loguru.py` | Python | [loguru](https://loguru.readthedocs.io/) | `pip install loguru>=0.7.0` |
| `nodejs_winston.js` | Node.js | [winston](https://github.com/winstonjs/winston) | `npm install winston winston-daily-rotate-file` |
| `nodejs_pino.js` | Node.js | [pino](https://getpino.io/) | `npm install pino pino-multi-stream` |
| `ruby_semantic_logger.rb` | Ruby | [semantic_logger](https://logger.rocketjob.io/) | `gem 'semantic_logger'` |
| `go_zap.go` | Go | [uber-go/zap](https://github.com/uber-go/zap) | `go get go.uber.org/zap@latest` |

---

## Primary vs. Alternative templates

AutoFix selects one **primary** framework per language when performing automatic
logging standardisation:

| Language | Primary framework | File |
|----------|-------------------|------|
| `python` | structlog | `python_structlog.py` |
| `nodejs` | winston | `nodejs_winston.js` |
| `ruby` | semantic_logger | `ruby_semantic_logger.rb` |
| `go` | zap | `go_zap.go` |

The alternative templates (`python_loguru.py`, `nodejs_pino.js`) are provided for
projects that already use those libraries or prefer them. The Claude agent may
reference them when it detects the alternative library already installed.

---

## Canonical JSON log schema

All templates produce JSON log lines conforming to this schema:

```json
{
  "timestamp": "<ISO 8601 UTC with milliseconds>",
  "level":     "<debug | info | warning | error | critical>",
  "logger":    "<module.or.class.path>",
  "message":   "<human-readable description>",
  "context":   { "<arbitrary key-value pairs>" },
  "error": {
    "type":    "<ExceptionClass>",
    "message": "<exception message>",
    "stack":   "<full stack trace>"
  }
}
```

AutoFix monitors for log lines where `"level"` is one of:
`error`, `critical`, `fatal`, `dpanic`, `panic`

---

## Usage by the Claude agent

1. The agent reads the appropriate snippet file (e.g. `python_structlog.py`).
2. It adapts the snippet to the target project's structure (correct import path,
   entry-point file, log path from config).
3. It places the adapted logging configuration file in the project repo.
4. It updates the project's main entry point to call `configure_logging()` early.
5. It adds the logging library to the project's dependency manifest.
6. It commits and pushes the changes, then triggers a container redeploy on the VPS.

---

## Adding a new template

1. Create a file following the naming convention `<language>_<framework>.<ext>`.
2. Include the following sections in the file (as comments):
   - Install instruction
   - Logging configuration function / initializer
   - Example usage showing info, warn, error, and exception patterns
3. Update this README table.
4. Update `_FRAMEWORK_MAP` and `_TEMPLATE_FILE_MAP` in `autofix/claude_launcher.py`
   if the new template should become the primary for its language.

