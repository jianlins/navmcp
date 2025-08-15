import markdownify

def test_html_fragment_to_markdownify():
    html_fragment = """
    <div id="article-details">
        <h1>Test Title</h1>
        <p>This is a <strong>test</strong> paragraph.</p>
    </div>
    """
    result = markdownify.markdownify(html_fragment, heading_style="ATX")
    print("Markdownify output:")
    print(result)
    # Check if output is markdown (not HTML)
    assert "# Test Title" in result or "Test Title" in result
    assert "<div" not in result
    assert "<h1>" not in result
    assert "<p>" not in result

if __name__ == "__main__":
    test_html_fragment_to_markdownify()
