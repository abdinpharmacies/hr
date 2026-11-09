workspace "LLM serving" "High-level architecture for an LLM inference service" {
  model {
    user = person "Application user"
    platform = softwareSystem "LLM platform" {
      gateway = container "API gateway" "Authentication, rate limits, request shaping" "Go"
      router = container "Model router" "Selects a model and routes requests" "Python"
      inference = container "Inference workers" "Runs decoder-only Transformer inference" "CUDA / PyTorch"
      cache = container "KV cache" "Stores attention keys and values for active sessions" "Redis" {
        tags "Database"
      }
      weights = container "Model weights" "Versioned checkpoint and tokenizer artifacts" "Object storage" {
        tags "Database"
      }
      telemetry = container "Telemetry" "Latency, token usage and quality signals" "OpenTelemetry"
    }
    user -> gateway "Sends prompts" "HTTPS/JSON"
    gateway -> router "Authorizes and forwards" "gRPC"
    router -> inference "Dispatches generation" "gRPC"
    inference -> cache "Reads and writes KV state" "Redis protocol"
    inference -> weights "Loads model artifacts" "HTTPS"
    inference -> telemetry "Emits metrics" "OTLP"
  }
  views {
    systemContext platform "context" {
      include *
      autolayout lr
    }
    container platform "containers" {
      include *
      autolayout lr
    }
  }
}
