from powerpaleontology_core import BBox, Block, Page, ParsedDocument


def test_can_create_parsed_document():
    bbox = BBox(x0=0.0, y0=0.0, x1=100.0, y1=50.0)

    page = Page(page_no=1, width=612, height=792)

    block = Block(
        block_id="doc-1-page-1-block-1",
        page_no=1,
        text="A new specimen of Triassic ichthyosaur.",
        section="Introduction",
        bbox=bbox,
    )

    document = ParsedDocument(
        document_id="doc-1",
        source_path="data/sample.pdf",
        title="A new ichthyosaur specimen",
        pages=[page],
        blocks=[block],
    )

    assert document.document_id == "doc-1"
    assert document.blocks[0].text.startswith("A new specimen")
    assert document.blocks[0].bbox == bbox