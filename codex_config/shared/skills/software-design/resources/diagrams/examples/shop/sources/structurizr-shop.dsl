workspace "Shop" "Order processing architecture" {
  model {
    customer = person "Customer"
    shop = softwareSystem "Shop" {
      web = container "Web App" "Customer storefront" "React"
      api = container "Order API" "Accepts and tracks orders" "ASP.NET Core"
      db = container "Order DB" "Stores orders" "PostgreSQL" {
        tags "Database"
      }
      queue = container "Message Queue" "Delivers domain events" "RabbitMQ" {
        tags "Queue"
      }
      worker = container "Email Worker" "Sends order email" ".NET Worker"
    }
    customer -> web "Browses and orders" "HTTPS"
    web -> api "Creates orders" "HTTPS/JSON"
    api -> db "Reads and writes" "SQL/TLS"
    api -> queue "Publishes OrderPlaced" "AMQP"
    queue -> worker "Delivers events" "AMQP"
  }
  views {
    systemContext shop "context" {
      include *
      autolayout lr
    }
    container shop "containers" {
      include *
      autolayout lr
    }
  }
}
