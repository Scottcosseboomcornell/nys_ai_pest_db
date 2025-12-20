# NYSPAD Parallel Search Scraper

## 🚀 Overview

The `new_NY_scraper_search.py` script now supports **parallel browser processing** to significantly speed up PDF downloads!

## ✨ Features

- **Up to 6 concurrent browsers** running simultaneously
- **Rate limiting**: New browsers start every 10 seconds (configurable)
- **Intelligent queue management**: As browsers finish, new ones start automatically
- **Thread-safe logging**: Easy to track progress of each browser
- **Maintains respectful scraping**: Controlled start delays prevent server overload

## 📋 Usage

### Basic Test (3 products, non-headless to see it work)
```bash
python3 new_NY_scraper_search.py --headless=False --max-products=3
```

### Production Run (all products with default 6 browsers)
```bash
python3 new_NY_scraper_search.py --headless=True
```

### Custom Configuration
```bash
python3 new_NY_scraper_search.py \
  --headless=True \
  --max-workers=4 \
  --start-delay=15.0 \
  --max-products=100
```

## ⚙️ Command-Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--headless` | bool | False | Run browsers in headless mode |
| `--max-products` | int | None (all) | Maximum products to process |
| `--max-workers` | int | 6 | Maximum concurrent browsers |
| `--start-delay` | float | 10.0 | Seconds between starting browsers |
| `--delay` | float | 2.0 | Internal operation delays |
| `--csv` | str | current_products_edited.csv | Path to CSV file |

## 📊 Performance Comparison

| Method | Time for 100 Products | Browsers |
|--------|----------------------|----------|
| Sequential (old) | ~150 minutes | 1 |
| Parallel (6 workers) | ~25-30 minutes | 6 |
| **Speed-up** | **~5-6x faster** | |

## 🔍 Log Format

Each browser instance is tagged with its number for easy tracking:

```
[Browser 1/100] Starting scrape for: PRODUCT NAME
[Browser 2/100] Found search input for PRODUCT NAME
[Browser 1/100] ✓ Successfully scraped: PRODUCT NAME
[Browser 3/100] Starting browser instance (Active: 3/6)...
```

## 🎯 How It Works

1. **Initialization**: Loads all products that need PDFs from CSV
2. **Thread Pool**: Creates a pool of up to `max-workers` threads
3. **Rate Limiting**: Each thread waits `start-delay` seconds after the previous start
4. **Independent Browsers**: Each thread creates its own Chrome instance
5. **Search & Scrape**: Each browser searches, finds, and downloads independently
6. **Auto-Queue**: When a browser finishes, a new one starts (if more products remain)
7. **Cleanup**: All browsers close automatically when done

## 🛡️ Safety Features

- **Rate limiting** prevents overwhelming the server
- **Thread-safe** operations ensure no data corruption
- **Independent sessions** prevent interference between browsers
- **Automatic retry** on stale elements
- **Graceful shutdown** ensures all browsers close properly

## 💡 Tips

1. **Start small**: Test with `--max-products=5` first
2. **Monitor resources**: 6 browsers use significant RAM (plan for ~3-4GB)
3. **Adjust workers**: Use `--max-workers=3` on less powerful machines
4. **Increase delay**: Use `--start-delay=15` if server seems slow
5. **Headless for production**: Always use `--headless=True` for long runs

## 🐛 Troubleshooting

### "Too many browsers crashing"
- Reduce `--max-workers` to 3 or 4
- Increase `--start-delay` to 15.0

### "Server seems slow/timing out"
- Increase `--start-delay` to 15.0 or 20.0
- Reduce `--max-workers` to 3

### "Out of memory"
- Reduce `--max-workers` to 3
- Close other applications

## 📈 Expected Output

```
============================================================
NYSPAD Parallel Search Scraper
============================================================
Max concurrent browsers: 6
Start delay: 10.0s
Headless mode: False
Products to process: ALL
============================================================

[Browser 1/10472] Starting browser instance (Active: 1/6)...
[Browser 1/10472] Starting scrape for: PRODUCT A
[Browser 2/10472] Rate limiting: waiting 10.0s before starting...
[Browser 2/10472] Starting browser instance (Active: 2/6)...
[Browser 1/10472] ✓ Successfully scraped: PRODUCT A
[Browser 1/10472] Closed browser for: PRODUCT A
[Browser 3/10472] Starting browser instance (Active: 3/6)...
...

============================================================
Parallel search-based scraping completed!
Successfully processed: 10450
Failed: 22
Total browsers used: 10472
============================================================
```

## 🎉 Enjoy faster scraping!


