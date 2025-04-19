# AutoAgentDesk - An AI agent for log analytics and querying

AutoAgentDesk is an AI agent designed to assist with log analytics and querying. You can interact with your logs from various sources, including frontend logs, backend logs, and database logs. The agent is capable of performing a wide range of tasks, including:
- Analyzing logs
- Querying logs
- Generating reports
- Visualizing data (yet to be implemented)
- Answering questions about logs
- Generating insights

## Technology Stack
- Python
- Gemini AI API - (to be replaced with OpenAI API)
- Fluvio (for log streaming) - (status: in progress)
- LangChain (for natural language processing)
- Chromadb (for vector storage)
- FastAPI (for building APIs)
- Docker (for containerization) - not yet implemented
- Redis (for caching) - not yet implemented
- PostgreSQL (for database storage) - not yet implemented

## Installation
To install AutoAgentDesk, clone the repository and install the required dependencies:

```bash
git clone https://github.com/rohittcodes/autoagentdesk
cd autoagentdesk
pip install -r requirements.txt
```

Note: For this prototype, we are just dumping the logs into a file. We're working on integrating with Fluvio for log streaming. The integration is in progress, and we will update the documentation once it's complete.

## Usage
Before using AutoAgentDesk, make sure to set up the necessary environment variables for the Gemini AI API and any other required configurations. You can do this by creating a `.env` file in the root directory of the project and adding the following lines from the `.env_sample` file:

```bash
FLUVIO_TOPIC=logs
CHROMA_DB_PATH=./chroma_db
GOOGLE_API_KEY=your_google_api_key
LOG_RETENTION_DAYS=30
MAX_BATCH_SIZE=100
PROCESSING_INTERVAL=5
```

Once you have set up the environment variables, you can start the FastAPI server:
Note: Don't forget to setup `Fluvio`, and start your virtual environment using `source venv/bin/activate` command.

```bash
python main.py
```

You can then access the API at `http://localhost:8000`. The API provides endpoints for interacting with the AI agent, including sending log data, querying logs, and generating reports.

## API Endpoints
- `/logs`: Endpoint for analyzing logs. You can access this endpoint to send log data to the AI agent for analysis. The agent will process the logs and return insights based on the data.
- `/queries`: Endpoint for querying logs. You can send a query to this endpoint, and the AI agent will return the relevant log data.
`curl -X POST "http://localhost:8000/queries/" -H "Content-Type: application/json" -d '{"query": "What WARN level logs occurred in the API service in the last 24 hours?", "max_logs": 100}'`
- `/report`: Endpoint for generating reports. You can send a request to this endpoint, and the AI agent will generate a report based on the log data. (yet to be implemented)

## Roadmap

- [ ] Implement visualization capabilities
- [ ] Add support for more log sources
- [ ] Improve natural language understanding
- [ ] Enhance performance and scalability
- [ ] Add more advanced analytics features
- [ ] Implement user authentication and authorization
- [ ] Create a web interface for easier interaction
- [ ] Add support for real-time log monitoring
- [ ] Implement alerting and notification features
- [ ] Add support for more languages
- [ ] Improve documentation and examples
- [ ] Add more test cases and improve test coverage
- [ ] Implement a plugin system for extensibility
- [ ] Add support for more data formats (e.g., JSON, XML)

## Contributing
We welcome contributions to AutoAgentDesk! If you have ideas for new features, improvements, or bug fixes, please open an issue or submit a pull request. Please make sure to follow the [contribution guidelines](CONTRIBUTING.md) when contributing to the project.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.