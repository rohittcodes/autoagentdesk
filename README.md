# AutoAgentDesk - An AI agent for log analytics and querying

AutoAgentDesk is an AI agent designed to assist with log analytics and querying. You can interact with your logs from various sources, including frontend logs, backend logs, and database logs. The agent is capable of performing a wide range of tasks, including:
- Analyzing logs
- Querying logs
- Generating reports
- Visualizing data (yet to be implemented)
- Answering questions about logs
- Generating insights
## Architecture Diagrams & Snapshots

<details>
  <summary><strong>Click to view architecture diagrams and snapshots</strong></summary>
  <br/>
  
  ### Architecture Diagrams
  
  ![llm-groq](https://github.com/user-attachments/assets/f56899ed-e364-4dee-bc6f-f828aeb828ec)  
  ![fluvio](https://github.com/user-attachments/assets/18a4aa95-5b9d-45a2-8a7d-fba8c2799ae8)  
  ![architecture](https://github.com/user-attachments/assets/21fca950-0ab3-452b-b389-0ac58fdcb2ff)  
  ![dataflow](https://github.com/user-attachments/assets/8f889f96-3d29-4be8-909d-e900ec380be7)

  ### Snapshots
  #### File ingestion  
  ![file-ingestion](https://github.com/user-attachments/assets/bf2f5e84-5e04-4a9f-8f83-1d6d66e5f315)
  #### Analysis Report  
  ![analysis-report](https://github.com/user-attachments/assets/b0e791c4-c219-407a-9715-31eea8bd16a1)
  #### Timeline  
  ![timeline](https://github.com/user-attachments/assets/83b159b1-cbac-42c3-9676-65195af42587)
  #### Agent state  
  ![agent-state](https://github.com/user-attachments/assets/312a5855-5194-4c18-81f5-42ce858c3938)

</details>

## Technology Stack
- Python
- MultiModel support (Groq AI, Gemini AI, OpenAI, Anthropic)
- Fluvio (for log streaming)
- LangChain
- Chromadb
- FastAPI
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

> Note: There are other sources like Redis, PostgreSQL, and Docker that are yet to be implemented.

You can pass any AI model you want to use for log analysis. Currently, we have implemented support for Groq AI, Gemini AI, OpenAI, and Anthropic. You can choose the model you want to use by setting the `MODEL` environment variable in your `.env` file.

Populate the `chromadb` database with the logs you want to analyze. You can use the `populate_logs.py` script to do this. The script will read the logs from a specified file and populate the database with the log entries.

```bash
python populate_logs.py
```
this will create a `chromadb` database in the current directory with the logs you want to analyze.

## Usage
Before using AutoAgentDesk, make sure to set up the necessary environment variables for the Gemini AI API and any other required configurations. You can do this by creating a `.env` file in the root directory of the project and adding the following lines from the `.env_sample` file:

```bash
FLUVIO_TOPIC=logs
CHROMA_DB_PATH=./chroma_db
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
DEFAULT_PROVIDER=google
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

- [x] Implement visualization capabilities
- [x] Add support for more log sources
- [x] Improve natural language understanding
- [ ] Enhance performance and scalability
- [ ] Add more advanced analytics features
- [ ] Implement user authentication and authorization
- [x] Create a web interface for easier interaction
- [ ] Update the web interface to use ReactJS
- [x] Add support for real-time log monitoring
- [ ] Implement alerting and notification features
- [ ] Add support for more languages
- [ ] Improve documentation and examples
- [ ] Add more test cases and improve test coverage
- [ ] Implement a plugin system for extensibility
- [x] Add support for more log formats (e.g., JSON, XML)

## Contributing
We welcome contributions to AutoAgentDesk! If you have ideas for new features, improvements, or bug fixes, please open an issue or submit a pull request. Please make sure to follow the [contribution guidelines](CONTRIBUTING.md) when contributing to the project.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
