# Personal Content Intelligence Agent
A high-performance, containerized Python framework designed to aggregate, synthesize, and deliver personalized insights from a curated list of digital sources. This system automates the bridge between high-volume content (YouTube, Blogs, RSS) and actionable intelligence.

## 🚀 Key Capabilities
Agnostic Ingestion: Seamlessly track any YouTube channel via RSS and extract full-text content from any web-based blog or article.

Custom Persona Synthesis: Leverages an agentic LLM layer that interprets raw data through the lens of a specific user-defined system prompt to generate high-signal summaries.

Structured Data Persistence: Organizes information into a relational PostgreSQL schema (Sources vs. Articles) using SQLAlchemy for easy querying and historical tracking.

Scheduled Intelligence: Designed for 24-hour execution cycles, culminating in a professionally formatted HTML digest sent via email.

Modern Infrastructure: Built with uv for ultra-fast dependency management and Docker for consistent environment orchestration.

## 🛠️ Technical Stack
Language: Python 
Package Management: uv (Fastest-in-class) 
Database: PostgreSQL 
ORM: SQLAlchemy 
Containers: Docker 
Integrations: OpenAI/Anthropic (Summarization), SMTP (Email Delivery)