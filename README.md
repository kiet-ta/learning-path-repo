# Auto Learning Path Generator

🚀 **Automatically generate personalized learning paths from your code repositories**

## Overview

The Auto Learning Path Generator is an intelligent system that analyzes your repositories to create structured learning roadmaps. It uses AI/NLP to understand your codebase, classify skills, and generate optimal learning sequences from basic to advanced topics.

## Features

- 🔍 **Auto Repository Scanning**: Automatically scans all local repositories
- 🧠 **AI-Powered Analysis**: Uses NLP to extract topics, skills, and dependencies
- 🗺️ **Interactive Roadmap**: Visual learning path similar to roadmap.sh
- 📊 **Progress Tracking**: Automatic progress monitoring based on git activity
- 📤 **Export Options**: Generate PDF/HTML reports for team sharing
- 🎯 **Customizable**: Override AI suggestions with manual adjustments

## Architecture

Built with Clean Architecture principles:

- **Domain Layer**: Core business logic and entities
- **Application Layer**: Use cases and services
- **Infrastructure Layer**: AI engine, file system, database
- **Interface Layer**: API and CLI interfaces

## Tech Stack

### Backend
- Python 3.9+
- FastAPI for REST API
- SQLite for data storage
- OpenAI/LangChain for NLP analysis
- GitPython for repository analysis

### Frontend
- React 18+
- D3.js for interactive visualizations
- Redux Toolkit for state management
- Tailwind CSS for styling

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 16+
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/kiet-ta/learning-path-repo.git
cd learning-path-repo
```

2. Backend setup:
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn interfaces.api.main:app --reload
```

3. Frontend setup:
```bash
cd frontend
npm install
npm start
```

4. Open http://localhost:3000 in your browser

## Usage

1. **Scan Repositories**: The system automatically scans your local repositories
2. **View Roadmap**: Interactive visualization shows your learning path
3. **Track Progress**: Monitor your learning progress automatically
4. **Export Results**: Generate reports for team sharing

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# AI Configuration
OPENAI_API_KEY=your_openai_key
MODEL_NAME=gpt-3.5-turbo

# Database
DATABASE_URL=sqlite:///learning_path.db

# Repository Scanning
REPO_SCAN_PATH=/path/to/your/repos
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Author

**TAK** - Auto Learning Path Generator Project

---

*Built with ❤️ for developers who want to optimize their learning journey*
# learning-path-repo
