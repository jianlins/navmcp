# Development Guide for navmcp

## Development

### Running Tests

```powershell
# Install test dependencies (included in requirements.txt)
pip install -r requirements.txt

# Run smoke tests (server must be running)
pytest tests/test_smoke_http.py -v

# Run basic tool tests (requires browser)
pytest tests/test_tools_basic.py -v

# Skip browser tests in CI
$env:SKIP_BROWSER_TESTS="1"
pytest -v
```

### Project Structure

```
navmcp/
├── app.py              # FastMCP server and SSE entrypoint
├── browser.py          # Selenium driver lifecycle management
├── tools/              # MCP tool implementations
│   ├── fetch.py        # fetch_url tool
│   ├── parse.py        # find_elements tool  
│   ├── interact.py     # click_element, run_js_interaction
│   ├── pdf.py          # download_pdfs tool
│   ├── convert.py      # convert_to_markdown, convert_file_to_markdown tools
│   ├── save.py         # save_file, fetch_and_save_url tools
│   ├── control.py      # start/stop/restart/shutdown tools
│   └── search.py       # web_search tool
├── utils/              # Shared utilities
│   ├── io.py           # Path and file utilities
│   ├── net.py          # URL validation and security
│   └── parsing.py      # HTML/selector utilities
├── tests/              # Test suites
├── .data/              # Data directory (downloads, logs)
├── requirements.txt    # Python dependencies
└── .env.example        # Environment configuration template
```

## Contributing

We welcome contributions! To contribute:

1. **Fork the repository** and create your branch from `main`.
2. **Code style**: Follow [PEP8](https://peps.python.org/pep-0008/) and use type annotations. Run `black` and `ruff` before submitting.
3. **Testing**: Add or update tests in the `tests/` directory. Run all tests with:
  ```powershell
  pytest tests/
  ```
  Make sure your changes pass on Windows and Linux.
4. **Pull Requests**: Open a PR with a clear description of your changes and reference any related issues.
5. **Documentation**: Update the README and docstrings as needed.

> For major changes, open an issue first to discuss your proposal.

## Changelog

### v1.0.0
- Initial release with 14 tools (browser control, fetch, parse, interact, PDF, conversion, file ops, search, shutdown)
- SSE transport with FastMCP
- Chrome automation with Selenium
- Security features and error handling
- Client configuration examples
