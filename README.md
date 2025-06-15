![github-submission-banner](https://github.com/user-attachments/assets/a1493b84-e4e2-456e-a791-ce35ee2bcf2f)

# 🚀 AutoAgentDesk

> An AI agent for log analytics and querying.

---

## 📌 Problem Statement

**Problem Statement 3 – Real-Time Data Experiences**

---

## 🎯 Objective

AutoAgentDesk addresses the challenges of log analytics and querying by providing an AI-powered solution that simplifies the process. It enables users to interact with logs in natural language, analyze them in real-time, and generate actionable insights.

- **Problem:**  
  - Log analytics is time-consuming and complex, especially with large datasets from multiple sources.
  - Traditional tools lack real-time capabilities and require manual intervention.
- **Solution:**  
  - AutoAgentDesk automates log analytics and querying with an AI agent that supports natural language interaction.
  - It provides real-time insights, report generation, and multi-source log integration.
- **Target Audience:**  
  - Developers, DevOps engineers, and data analysts.
  - Organizations needing real-time log monitoring and analytics.
- **Value Proposition:**  
  - Saves time and reduces complexity in log analysis.
  - Makes log querying accessible to non-technical users.
  - Enables faster issue resolution with real-time capabilities.

---

## 🧠 Team & Approach

### Team Name:  
`AutoAgentDesk` (Solo hacker)

### Team Members:  
- Rohith Singh (Team Lead)

### Approach:  
- Researched existing tools and identified gaps.
- Designed a scalable architecture for real-time log processing and natural language interaction.
- Built the core functionality using Python, FastAPI, LangChain, and Chromadb.
- Integrated Chromadb for log storage and trained the AI on diverse log queries.
- Created a web interface for user-friendly interaction.
- Iteratively improved the agent based on feedback.

---

## 🛠️ Tech Stack

### Core Technologies:
- **Frontend:** HTML, CSS, JavaScript (ReactJS)
- **Backend:** Python, FastAPI
- **Database:** Chromadb, PostgreSQL
- **APIs:** LangChain (NLP)
- **AI Models:** Groq AI, Gemini AI, OpenAI, Anthropic
- **Hosting:** Docker (containerization), Redis (caching) - not yet implemented
- **Other Tools:** GitHub (version control), Postman (API testing)

---

## ✨ Key Features

- ✅ Multi-model AI support (Groq AI, Gemini AI, OpenAI, Anthropic)  
- ✅ Natural language querying for logs  
- ✅ Multi-source log integration (frontend, backend, database)  
- ✅ RESTful API and web interface  
- ✅ Plugin system for extensibility  
- ✅ Support for JSON, XML, and other log formats  
- ✅ Timeline tracking and state management  
- ✅ Report generation and batch processing  

---

## 📽️ Demo & Deliverables

- **Demo Video Link:** [YouTube](https://youtu.be/HslDdRlI48Q)  
- **Pitch Deck / PPT Link:** [Google Slides](https://docs.google.com/presentation/d/1ZF7uGd7cZEL1pabyFeWnp1DSQmmJWnp0eutTnlmVXIE/edit?usp=sharing)  

---

## 🧪 How to Run the Project

### Requirements:
- **Python 3.8+**: Ensure Python is installed on your system.
- **Node.js**: Required for the frontend (if applicable).
- **Docker**: For containerization (optional, not yet implemented).
- **API Keys**: Required for AI models and services:
  - `GROQ_API_KEY`
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GOOGLE_API_KEY`
- **Environment Variables**: Set up a `.env` file in the root directory. Refer to the `.env_sample` file for required variables.
- **Chromadb**: For log storage.
- **PostgreSQL**: For database storage (optional, not yet implemented).
- **Redis**: For caching (optional, not yet implemented).

### Local Setup:
```bash
git clone https://github.com/rohittcodes/autoagentdesk

cd autoagentdesk
pip install -r requirements.txt

python main.py
```

Access the API at `http://localhost:8000`.

---

## 🧬 Architecture Diagrams & Snapshots

<details>
  <summary><strong>Click to view architecture diagrams and snapshots</strong></summary>
  <br/>
  
  ### Architecture Diagrams
  
  ![llm-groq](https://github.com/user-attachments/assets/f56899ed-e364-4dee-bc6f-f828aeb828ec)  
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

---

## 🧬 Future Scope

- 📈 Add more integrations and advanced analytics features.  
- 🛡️ Enhance security and scalability.  
- 🌐 Support localization and multi-language capabilities.  
- 🔔 Implement alerting and notification systems.  
- 🖥️ Improve the web interface with ReactJS.  

---

## 📎 Resources / Credits

- APIs: LangChain, Groq AI,  OpenAI, Anthropic  
- Tools: Chromadb, FastAPI, Docker, Redis  
- Acknowledgements: HackHazards team and community  

---

## 🏁 Final Words
My hackathon journey building AutoAgentDesk has been both challenging and rewarding! Here's a glimpse into my experience:

### Challenges & Learnings
- Working with ChromaDB's query format was a significant hurdle. When implementing filters, I discovered that ChromaDB has specific requirements for field names and operators. After debugging the "Invalid where clause" errors, I learned the importance of proper field name mapping and using the correct query operators (`$in` vs `$eq`).
- The context variable definition bug in the LogAnalysisAgent class taught me to be more careful about variable scoping in asynchronous Python code. Always capture return values!
- Balancing token limits with comprehensive log analysis was tricky. I developed a smart log prioritization system that ensures critical database and memory-related errors are never truncated, even when dealing with thousands of logs.

### Technical Insights
- Integrating Groq's API was seamless once I understood its token limitations. The performance improvement over other models for this specific use case was impressive - responses are noticeably faster.
- Building a context-aware AI agent that maintains conversation history and previous findings created a more natural and insightful user experience than I initially expected.

### Community & Inspiration
- Special thanks to the Groq and InfinyOn teams for their documentation and sample projects that helped make integration smoother.

I'm excited to continue developing AutoAgentDesk beyond this hackathon, with plans to implement the alerting system and ReactJS frontend improvements next. This project has deepened my understanding of AI-assisted observability tools and real-time data processing architectures.

---

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
