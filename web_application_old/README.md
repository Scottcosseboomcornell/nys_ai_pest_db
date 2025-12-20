# Cosseboom Lab Web Application

This is the web application for Cosseboom Lab, providing access to research tools and databases.

## Website Structure

- **Homepage** (`/`): Main landing page with links to all projects
- **Pesticide Database** (`/pesticide-database`): Search and explore pesticide information from EPA labels

## Available Applications

### 1. Pesticide Database
A comprehensive database of agricultural pesticides with detailed information, search capabilities, and regulatory data to support research and decision-making in crop protection.

**Features:**
- Search by EPA registration number or trade name
- Detailed pesticide information
- Active ingredient details
- Safety and PPE information
- Company information

## Deployment

### Quick Deployment (New Instance)
```bash
./quick_deploy.sh
```

### Full Deployment (Existing Instance)
```bash
./deploy_final.sh /path/to/your/key.pem
```

## Development

### Local Development
1. Install dependencies:
   ```bash
   pip install flask mysql-connector-python python-dotenv
   ```

2. Set up environment variables in `.env`:
   ```
   DB_HOST=your_database_host
   DB_PORT=3306
   DB_USER=your_username
   DB_PASSWORD=your_password
   DB_NAME=your_database_name
   ```

3. Run the application:
   ```bash
   python web_app.py
   ```

### File Structure
```
web_application/
├── web_app.py              # Main Flask application (database version)
├── pesticide_search.py     # Simple Flask application (JSON version)
├── templates/
│   ├── homepage.html       # New homepage
│   ├── index.html          # Pesticide database interface
│   └── search.html         # Search interface
├── deploy_final.sh         # Full deployment script
├── quick_deploy.sh         # Quick deployment script
└── README.md              # This file
```

## API Endpoints

### Health Check
- `GET /api/health` - Check system health and database connectivity

### Pesticide Data
- `GET /api/pesticides` - Get pesticides with optional search parameters
- `GET /api/pesticides/<id>` - Get specific pesticide by ID
- `GET /api/stats` - Get database statistics

### Search (JSON version)
- `GET /api/search` - Search pesticides by EPA reg number or trade name
- `GET /api/pesticide/<epa_reg_no>` - Get specific pesticide details

## Future Projects

The homepage is designed to accommodate additional research tools and databases as they become available. Each new project can be added as a new card in the projects grid on the homepage. 