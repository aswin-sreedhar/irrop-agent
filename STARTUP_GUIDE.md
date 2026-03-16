# Startup Guide — Airline Disruption Agent

This guide will help you set up and run the Airline Disruption Agent on a new machine from scratch.

## Prerequisites

Before you begin, ensure you have the following installed on your machine:

### 1. Python 3.13+
Check if Python is installed:
```bash
python3 --version
```

If not installed, download from [python.org](https://www.python.org/downloads/) or use your package manager:
- **macOS**: `brew install python@3.13`
- **Linux (Ubuntu/Debian)**: `sudo apt update && sudo apt install python3.13`
- **Windows**: Download installer from python.org

### 2. Git
Check if Git is installed:
```bash
git --version
```

If not installed:
- **macOS**: `brew install git`
- **Linux (Ubuntu/Debian)**: `sudo apt install git`
- **Windows**: Download from [git-scm.com](https://git-scm.com/)

### 3. Anthropic API Key
You'll need an API key from Anthropic to use Claude Sonnet 4.5.

1. Visit [console.anthropic.com](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Save it securely (you'll need it in Step 4)

## Step-by-Step Setup

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/aswin-sreedhar/irrop-agent.git

# Navigate into the project directory
cd irrop-agent
```

### Step 2: Create a Virtual Environment

Creating a virtual environment isolates your project dependencies from your system Python.

```bash
# Create virtual environment
python3 -m venv venv
```

### Step 3: Activate the Virtual Environment

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows (Command Prompt):**
```bash
venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```bash
venv\Scripts\Activate.ps1
```

You should see `(venv)` appear at the beginning of your terminal prompt.

### Step 4: Configure Environment Variables

Create a `.env` file in the project root directory:

```bash
# Create .env file
touch .env  # On Windows: type nul > .env
```

Open `.env` in your text editor and add your Anthropic API key:

```
ANTHROPIC_API_KEY=your_actual_api_key_here
```

**Important:** Replace `your_actual_api_key_here` with the API key you obtained from Anthropic.

### Step 5: Install Dependencies

Install all required Python packages:

```bash
pip install fastapi uvicorn langgraph langchain-anthropic python-dotenv sqlalchemy
```

**Expected output:** You should see packages being downloaded and installed.

### Step 6: Verify Installation

Check that all dependencies are installed correctly:

```bash
pip list
```

You should see packages like:
- `fastapi`
- `uvicorn`
- `langgraph`
- `langchain-anthropic`
- `python-dotenv`
- `sqlalchemy`

### Step 7: Start the Server

Launch the FastAPI server:

```bash
uvicorn main:app --reload
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

The `--reload` flag enables auto-restart when you modify code (useful for development).

### Step 8: Test the API

Open a new terminal (keep the server running in the first terminal) and test the endpoint:

```bash
curl -X POST http://127.0.0.1:8000/trigger-ssbres \
  -H "Content-Type: application/json" \
  -d '{"pnr": "STU901"}'
```

**Expected output:** You should see a JSON response with notification details for the test PNR.

Alternatively, visit `http://127.0.0.1:8000/docs` in your browser to access the interactive API documentation (Swagger UI).

## Project Structure

```
irrop-agent/
├── main.py                 # FastAPI application and LangGraph workflow
├── README.md              # Project documentation
├── STARTUP_GUIDE.md       # This file
├── .env                   # Environment variables (you create this)
├── .gitignore            # Git ignore rules
└── venv/                 # Virtual environment (created by you)
```

## Available API Endpoints

Once the server is running, you can access:

- **Interactive Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative Docs**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Main Endpoints:

1. **Process Disruption Message**
   ```bash
   POST /trigger-ssbres
   Body: {"pnr": "STU901"}
   ```

2. **Get PNR Details**
   ```bash
   GET /pnr/STU901
   ```

3. **List All PNRs**
   ```bash
   GET /pnrs
   ```

4. **Health Check**
   ```bash
   GET /health
   ```

## Testing with Sample Data

The system comes pre-seeded with test PNRs. Try these:

```bash
# Test cabin downgrade scenario
curl -X POST http://127.0.0.1:8000/trigger-ssbres \
  -H "Content-Type: application/json" \
  -d '{"pnr": "STU901"}'

# Test unaccommodated passenger scenario
curl -X POST http://127.0.0.1:8000/trigger-ssbres \
  -H "Content-Type: application/json" \
  -d '{"pnr": "ABC123"}'
```

Check the console output where your server is running to see the generated SMS and email notifications.

## Troubleshooting

### Issue: "ModuleNotFoundError"
**Solution:** Make sure you activated the virtual environment and installed all dependencies:
```bash
source venv/bin/activate  # or Windows equivalent
pip install fastapi uvicorn langgraph langchain-anthropic python-dotenv sqlalchemy
```

### Issue: "ANTHROPIC_API_KEY not found"
**Solution:**
1. Verify `.env` file exists in the project root
2. Check that it contains `ANTHROPIC_API_KEY=your_key`
3. Restart the server after creating/modifying `.env`

### Issue: "Address already in use"
**Solution:** Port 8000 is already taken. Either:
- Stop the other process using port 8000
- Or run on a different port: `uvicorn main:app --reload --port 8001`

### Issue: API calls return 500 errors
**Solution:**
1. Check the server console for error details
2. Verify your Anthropic API key is valid
3. Ensure you have API credits in your Anthropic account

### Issue: Virtual environment activation fails on Windows PowerShell
**Solution:** You may need to change the execution policy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Stopping the Server

To stop the server:
1. Go to the terminal where the server is running
2. Press `CTRL+C`

## Deactivating the Virtual Environment

When you're done working:
```bash
deactivate
```

## Next Steps

- Read [README.md](README.md) for detailed architecture and workflow documentation
- Explore the interactive API docs at `http://127.0.0.1:8000/docs`
- Modify `main.py` to customize the notification logic
- Add your own test PNRs to the seeded data

## Getting Help

If you encounter issues:
1. Check the server console for detailed error messages
2. Review the [README.md](README.md) for system architecture details
3. Verify all prerequisites are installed correctly
4. Ensure your Anthropic API key is valid and has sufficient credits

## Production Deployment Notes

This setup is for local development. For production deployment:
- Use a production-grade database (PostgreSQL/MySQL) instead of SQLite
- Set up proper environment variable management (not `.env` files)
- Configure HTTPS/SSL certificates
- Implement rate limiting and authentication
- Set up monitoring and logging infrastructure
- Use a production ASGI server configuration
- Integrate real SMS/email gateway APIs
