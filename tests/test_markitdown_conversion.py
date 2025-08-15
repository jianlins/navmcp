import io
from markitdown import MarkItDown

def test_html_fragment_to_markdown():
    html_fragment = """
    <div id="article-details">
        <h1>Test Title</h1>
        <p>This is a <strong>test</strong> paragraph.</p>
    </div>
    """
    md = MarkItDown(enable_plugins=False)
    stream = io.BytesIO(html_fragment.encode("utf-8"))
    result = md.convert(stream)
    print("Converted output:")
    print(result.text_content)
    # Check if output is markdown (not HTML)
    assert "# Test Title" in result.text_content or "Test Title" in result.text_content
    assert "<div" not in result.text_content
    assert "<h1>" not in result.text_content
    assert "<p>" not in result.text_content

if __name__ == "__main__":
    test_html_fragment_to_markdown()
