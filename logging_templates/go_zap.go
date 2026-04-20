// AutoFix Standard Logging — Go (uber-go/zap)
// =============================================
// Add to go.mod (run once):
//   go get go.uber.org/zap@latest
//   go get go.uber.org/zap/zapcore@latest
//
// Save this file as: internal/logger/logger.go
// Then call logger.Init() from main() before starting the application.
//
// Usage:
//   import "your-module/internal/logger"
//   log := logger.Get()
//   log.Info("server_started", zap.Int("port", 8080))
//   log.Error("db_connection_failed", zap.Error(err), zap.String("host", dbHost))
//
// The produced JSON matches the AutoFix canonical schema:
//   {"ts":"...","level":"error","caller":"main.go:42","msg":"...","key":"value"}
// AutoFix watches for lines where "level" is "error", "dpanic", "panic", or "fatal".

package logger

import (
	"os"
	"path/filepath"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

// LogPath is the file path where structured JSON logs are written.
// Override via the LOG_FILE environment variable before calling Init().
var LogPath = "logs/app.log"

// level is the minimum log level. Override via LOG_LEVEL env var.
var level = zapcore.InfoLevel

// global is the package-level zap logger returned by Get().
var global *zap.Logger

// Init configures the global JSON logger to write to both stdout and the log
// file at LogPath. Call this once from main() before any other logging.
func Init() error {
	// Resolve log path from environment if set
	if v := os.Getenv("LOG_FILE"); v != "" {
		LogPath = v
	}

	// Parse log level from environment
	if v := os.Getenv("LOG_LEVEL"); v != "" {
		if err := level.Set(v); err != nil {
			level = zapcore.InfoLevel // fallback
		}
	}

	// Ensure the log directory exists
	if err := os.MkdirAll(filepath.Dir(LogPath), 0o755); err != nil {
		return err
	}

	// Open the log file for writing (append mode)
	logFile, err := os.OpenFile(
		LogPath,
		os.O_CREATE|os.O_WRONLY|os.O_APPEND,
		0o644,
	)
	if err != nil {
		return err
	}

	// Production encoder config: ISO 8601 timestamps, lowercase level names
	encoderCfg := zapcore.EncoderConfig{
		TimeKey:        "timestamp",
		LevelKey:       "level",
		NameKey:        "logger",
		CallerKey:      "caller",
		FunctionKey:    zapcore.OmitKey,
		MessageKey:     "message",
		StacktraceKey:  "stacktrace",
		LineEnding:     zapcore.DefaultLineEnding,
		EncodeLevel:    zapcore.LowercaseLevelEncoder,
		EncodeTime:     zapcore.ISO8601TimeEncoder,
		EncodeDuration: zapcore.MillisDurationEncoder,
		EncodeCaller:   zapcore.ShortCallerEncoder,
	}

	// Tee: write JSON to both stdout (Docker) and the log file
	core := zapcore.NewTee(
		zapcore.NewCore(
			zapcore.NewJSONEncoder(encoderCfg),
			zapcore.AddSync(os.Stdout), // Docker `docker logs -f` reads stdout
			level,
		),
		zapcore.NewCore(
			zapcore.NewJSONEncoder(encoderCfg),
			zapcore.AddSync(logFile),
			level,
		),
	)

	global = zap.New(
		core,
		zap.AddCaller(),                          // include file:line
		zap.AddStacktrace(zapcore.ErrorLevel),    // stack trace on Error+
	)
	return nil
}

// Get returns the global logger. Panics if Init() has not been called.
func Get() *zap.Logger {
	if global == nil {
		panic("logger.Init() must be called before logger.Get()")
	}
	return global
}

// Sync flushes any buffered log entries. Defer this from main().
func Sync() {
	if global != nil {
		_ = global.Sync()
	}
}

// ---------------------------------------------------------------------------
// Example entry-point wiring (main.go):
// ---------------------------------------------------------------------------
//
// package main
//
// import (
//     "your-module/internal/logger"
//     "go.uber.org/zap"
// )
//
// func main() {
//     if err := logger.Init(); err != nil {
//         panic("failed to initialize logger: " + err.Error())
//     }
//     defer logger.Sync()
//
//     log := logger.Get()
//
//     // Informational event
//     log.Info("application_started",
//         zap.String("version", "1.0.0"),
//         zap.String("env", os.Getenv("APP_ENV")),
//     )
//
//     // Warning with context
//     log.Warn("database_connection_slow",
//         zap.Int("latency_ms", 850),
//         zap.String("host", dbHost),
//     )
//
//     // Error with error value — zap serializes err.Error() + type
//     if err := connectDB(); err != nil {
//         log.Error("database_connection_failed",
//             zap.Error(err),
//             zap.String("host", dbHost),
//         )
//     }
//
//     // Fatal — logs then calls os.Exit(1)
//     log.Fatal("startup_failed", zap.Error(startupErr))
// }
