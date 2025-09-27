# Database-Driven Newegg Scraper

An enterprise-ready web scraping solution for Newegg.com with CSV input processing, database-driven queues, and automatic retry mechanisms.

## 🏗️ Architecture Overview

### Database-First Workflow
1. **CSV Input** → Populate `scraping_sessions` table
2. **Scraper Daemon** → Poll database for pending work
3. **Parser Daemon** → Process completed scraping sessions
4. **Database** → Track all states and retry attempts

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **Orchestrator** | `orchestrator.py` | Main workflow coordinator |
| **CSV Processor** | `csv_processor.py` | Process CSV files into database |
| **Scraper Daemon** | `scraper_daemon.py` | Database-driven HTML & API fetching |
| **Parser Daemon** | `parser_daemon.py` | Database-driven data processing |
| **Database** | `database.py` | Enhanced SQLite with queue management |

## 📊 Database Schema

### Enhanced `scraping_sessions` Table
```sql
CREATE TABLE scraping_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE,
    product_id INTEGER,
    product_url TEXT,
    html_fetch_status TEXT DEFAULT 'pending',        -- pending/completed/failed
    review_fetch_status TEXT DEFAULT 'pending',      -- pending/completed/failed
    html_fetch_attempts INTEGER DEFAULT 0,           -- Max 3 attempts
    review_fetch_attempts INTEGER DEFAULT 0,         -- Max 3 attempts
    html_error_message TEXT,
    review_error_message TEXT,
    parsing_status TEXT DEFAULT 'pending',           -- pending/completed/failed
    html_file_location TEXT,                         -- Path to saved HTML
    review_data_location TEXT,                       -- Path to saved JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scraped_at TIMESTAMP,                            -- When scraping completed
    parsed_at TIMESTAMP,                             -- When parsing completed
    processed_at TIMESTAMP,                          -- When fully processed
    FOREIGN KEY (product_id) REFERENCES products (id)
);
```

## 🚀 Quick Start

### 1. Complete Workflow (Recommended)
```bash
# Process CSV and start all services
python orchestrator.py run urls.csv

# With custom settings
python orchestrator.py run urls.csv --scraper-poll=60 --batch-size=10
```

### 2. Step-by-Step Workflow
```bash
# Step 1: Process CSV file
python csv_processor.py urls.csv

# Step 2: Start scraper daemon (separate terminal)
python scraper_daemon.py start

# Step 3: Start parser daemon (separate terminal)
python parser_daemon.py start

# Step 4: Monitor progress
python orchestrator.py status
```

### 3. Create Sample CSV
```bash
# Generate sample URLs file
python csv_processor.py --create-sample sample_urls.csv
```

## 📄 CSV File Format

### Required Format
```csv
url,priority,notes
https://www.newegg.com/product1/p/N82E16824281334,normal,Gaming monitor
https://www.newegg.com/product2/p/N82E16824025909,high,4K monitor
```

### CSV Validation
- **Required column**: `url`
- **URL validation**: Must be valid Newegg product URLs
- **Duplicate detection**: Skips URLs already in pending state
- **Error reporting**: Shows invalid URLs with line numbers

## 🔄 Processing Flow

### 1. CSV Processing
```
CSV File → Validation → Database Records → Queue Ready
```

### 2. Scraping Flow
```
HTML Fetch (max 3 attempts) → Review Fetch (max 3 attempts) → Ready for Parsing
```

### 3. Parsing Flow
```
Parse HTML → Parse Reviews → Update Database → Mark Complete
```

## 🤖 Daemon Operations

### Scraper Daemon
```bash
# Start continuous scraping
python scraper_daemon.py start --poll-interval=30 --batch-size=5

# Process one batch only
python scraper_daemon.py run-once --batch-size=3

# Check status
python scraper_daemon.py status
```

**Features:**
- Polls database every 30 seconds (configurable)
- Processes up to 5 sessions per batch (configurable)
- Automatic retry with exponential backoff
- Session preservation between HTML and API calls
- Organized file storage with metadata

### Parser Daemon
```bash
# Start continuous parsing
python parser_daemon.py start --poll-interval=30 --batch-size=5

# Parse one batch only
python parser_daemon.py run-once --batch-size=3

# Check status
python parser_daemon.py status
```

**Features:**
- Processes sessions where both HTML and reviews are fetched
- Updates products and reviews tables
- Handles data validation and deduplication
- Automatic error handling and retry logic

## 📊 Monitoring & Status

### Real-time Status
```bash
# Overall system status
python orchestrator.py status

# CSV processing statistics
python csv_processor.py --stats

# Individual daemon status
python scraper_daemon.py status
python parser_daemon.py status
```

### Status Output Example
```
📊 NEWEGG SCRAPER STATUS
==================================================
📈 DATABASE STATISTICS:
   Total sessions: 150

🔍 HTML FETCH:
   completed: 120 (80.0%)
   pending: 25 (16.7%)
   failed: 5 (3.3%)

📊 REVIEW FETCH:
   completed: 115 (76.7%)
   pending: 30 (20.0%)
   failed: 5 (3.3%)

🔄 PARSING:
   completed: 110 (73.3%)
   pending: 35 (23.3%)
   failed: 5 (3.3%)

📈 OVERALL PROGRESS:
   Completion rate: 73.3% (110/150)
```

## 🛠️ Configuration

### Environment Variables
```bash
# Database configuration
export NEWEGG_DB_PATH="custom_scraper.db"
export NEWEGG_RAW_DATA_DIR="custom_raw_data"

# Daemon settings
export SCRAPER_POLL_INTERVAL=60
export PARSER_POLL_INTERVAL=30
export BATCH_SIZE=10
```

### Retry Logic
- **Maximum attempts**: 3 per operation
- **HTML fetch failures**: Marked as failed after 3 attempts
- **Review fetch failures**: Marked as failed after 3 attempts
- **Parsing failures**: Logged with error messages

### Performance Tuning
```bash
# High-throughput configuration
python orchestrator.py run urls.csv --scraper-poll=15 --batch-size=10

# Conservative configuration
python orchestrator.py run urls.csv --scraper-poll=120 --batch-size=3
```

## 📁 File Organization

### Data Structure
```
raw_data/
├── session_20241215_143022_0001/
│   ├── html/
│   │   └── successful_response_attempt_1.html
│   └── api_responses/
│       └── reviews_data.json
├── session_20241215_143023_0002/
│   ├── html/
│   │   └── successful_response_attempt_1.html
│   └── api_responses/
│       └── reviews_data.json
└── ...
```

### Database Files
```
newegg_scraper.db          # Main SQLite database
newegg_scraper.db-journal  # SQLite journal (temporary)
```

## 🔍 Troubleshooting

### Common Issues

**1. CSV Processing Errors**
```bash
# Validate CSV format
python csv_processor.py urls.csv --dry-run

# Check for invalid URLs
python csv_processor.py --stats
```

**2. Scraping Failures**
```bash
# Check failed sessions
python orchestrator.py status

# Review error messages in database
sqlite3 newegg_scraper.db "SELECT * FROM scraping_sessions WHERE html_fetch_status='failed';"
```

**3. Parsing Issues**
```bash
# Check file locations
ls -la raw_data/session_*/

# Manually test parser
python parser_daemon.py run-once
```

**4. Database Issues**
```bash
# Test database connection
python database.py

# Reset failed sessions (use carefully)
sqlite3 newegg_scraper.db "UPDATE scraping_sessions SET html_fetch_status='pending', html_fetch_attempts=0 WHERE html_fetch_status='failed';"
```

## 📈 Performance Metrics

### Typical Performance
- **CSV processing**: ~1000 URLs/second
- **HTML fetching**: ~10-20 products/minute (with delays)
- **Review fetching**: ~10-15 products/minute
- **Parsing**: ~50-100 sessions/minute

### Scaling Recommendations
- **Small scale (1-100 URLs)**: Default settings
- **Medium scale (100-1000 URLs)**: `--batch-size=10 --scraper-poll=30`
- **Large scale (1000+ URLs)**: `--batch-size=20 --scraper-poll=15`

## 🔐 Best Practices

### Operational
- Monitor scraper success rates (should be >90%)
- Check for rate limiting or bot detection
- Use reasonable batch sizes to avoid overwhelming servers
- Keep raw data backed up before processing

### Development
- Test with small batches first (`--batch-size=1`)
- Use dry-run mode for CSV validation
- Monitor database growth and clean old sessions
- Keep daemons running with process managers (systemd, supervisor)

## 📋 Example Workflows

### Production Batch Processing
```bash
# 1. Prepare CSV with 1000 URLs
python csv_processor.py large_batch.csv --dry-run

# 2. Process CSV
python csv_processor.py large_batch.csv

# 3. Start optimized workflow
python orchestrator.py run large_batch.csv --scraper-poll=15 --batch-size=15

# 4. Monitor in separate terminal
watch -n 30 "python orchestrator.py status"
```

### Development Testing
```bash
# 1. Create test data
python csv_processor.py --create-sample test_urls.csv

# 2. Test with small batch
python orchestrator.py run test_urls.csv --batch-size=2 --scraper-poll=10

# 3. Check results
python orchestrator.py status
```

### Recovery from Failures
```bash
# 1. Check what failed
python orchestrator.py status

# 2. Reset failed HTML fetches (if appropriate)
sqlite3 newegg_scraper.db "UPDATE scraping_sessions SET html_fetch_status='pending', html_fetch_attempts=0 WHERE html_fetch_status='failed';"

# 3. Restart scraper
python scraper_daemon.py start
```

---

**Enhanced Features:**
- ✅ Database-driven queue management
- ✅ Automatic retry mechanisms (3 attempts max)
- ✅ CSV input processing with validation
- ✅ Daemon-based continuous processing
- ✅ Comprehensive monitoring and status tracking
- ✅ Organized file storage with metadata
- ✅ Enterprise-ready error handling
- ✅ Scalable architecture for large batches