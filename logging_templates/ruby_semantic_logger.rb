# AutoFix Standard Logging — Ruby (semantic_logger)
# ====================================================
# Add to Gemfile:
#   gem 'semantic_logger', '>= 4.15'
#
# Then run: bundle install
#
# Add this initializer at:
#   Rails apps   → config/initializers/semantic_logger.rb
#   Sinatra/Rack → config.ru or app.rb (before Rack::Builder)
#   Plain Ruby   → lib/logging_config.rb  (require early in main entry point)
#
# Usage:
#   logger = SemanticLogger['MyClass']
#   logger.info('Server started', port: 8080)
#   logger.error('Database connection failed', exception: e, host: db_host)
#
# The produced JSON matches the AutoFix canonical schema:
#   {"timestamp":"...","level":"error","name":"MyClass","message":"...","host":"..."}
# AutoFix watches for lines where "level" is "error" or "fatal".

require 'semantic_logger'
require 'fileutils'

# ---------------------------------------------------------------------------
# Configuration — adjust LOG_PATH and LOG_LEVEL via environment variables
# ---------------------------------------------------------------------------
LOG_PATH  = ENV.fetch('LOG_FILE', 'logs/app.log')
LOG_LEVEL = ENV.fetch('LOG_LEVEL', 'info').to_sym

# Ensure logs directory exists
FileUtils.mkdir_p(File.dirname(LOG_PATH))

def configure_logging
  # Set minimum log level globally
  SemanticLogger.default_level = LOG_LEVEL

  # Remove any appenders added by Rails or other frameworks first
  SemanticLogger.appenders.each { |a| SemanticLogger.remove_appender(a) }

  # JSON file appender — structured JSON lines, compatible with log rotation
  file_appender = SemanticLogger::Appender::File.new(
    file_name: LOG_PATH,
    formatter: :json,          # JSON output
  )
  SemanticLogger.add_appender(file_appender)

  # Stdout appender — required for Docker `docker logs -f` compatibility
  # Uses the same JSON formatter
  stdout_appender = SemanticLogger::Appender::IO.new(
    $stdout,
    formatter: :json,
  )
  SemanticLogger.add_appender(stdout_appender)

  # Capture standard Ruby Logger output and route through SemanticLogger
  if defined?(Rails)
    Rails.logger = SemanticLogger['Rails']
  end
end

configure_logging

# ---------------------------------------------------------------------------
# Example usage (delete before committing to the application)
# ---------------------------------------------------------------------------
#
# # Get a logger bound to a class or module name
# logger = SemanticLogger['MyService']
#
# # Informational event with structured context
# logger.info('Application started', version: '1.0.0', env: ENV['RACK_ENV'])
#
# # Warning with context
# logger.warn('Database connection slow', latency_ms: 850, host: db_host)
#
# # Error with exception — SemanticLogger automatically extracts backtrace
# begin
#   connect_to_database
# rescue => e
#   logger.error('Database connection failed', exception: e, host: DB_HOST)
# end
#
# # Fatal error
# begin
#   risky_startup_step
# rescue => e
#   logger.fatal('Fatal startup error', exception: e)
#   exit 1
# end
