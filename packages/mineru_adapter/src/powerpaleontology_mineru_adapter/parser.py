# =====================================================================
# parser.py
# 这个文件负责把 MinerU 解析结果转换成项目内部的核心文档模型。
#
# MinerU 完成解析后，通常会返回一个 zip 文件。
# zip 中一般包含：
# - full.md        Markdown 格式的完整正文
# - layout.json    布局信息，后续可以用来提取页码和 bbox
# - 其他 JSON 文件  模型推理或中间处理结果
#
# 第一版 parser 采用比较稳的策略：
# 1. 从 zip 中找到 full.md；
# 2. 读取 Markdown 文本；
# 3. 按 Markdown 标题和段落切成 Block；
# 4. 生成一个 ParsedDocument。
#
# 注意：
# 这一版暂时不解析 layout.json，所以 page_no 暂时默认为 1。
# 后续接入 bbox 和真实页码时，可以升级这个文件。
# =====================================================================

# 启用现代化类型注解。
from __future__ import annotations

# io.BytesIO 用于把 bytes 包装成文件对象，交给 zipfile 读取。
import io

# re 用于识别 Markdown 标题、列表、表格等结构。
import re

# zipfile 用于读取 MinerU 返回的结果压缩包。
import zipfile

# pathlib.Path 用于表示本地 PDF 路径。
from pathlib import Path

# 导入项目核心模型。
# ParsedDocument 是全项目统一的文档模型。
# Page 和 Block 是 ParsedDocument 内部使用的结构。
from powerpaleontology_core import Block, Page, ParsedDocument

# 导入 MinerU Adapter 自己的异常类型。
# parser 遇到 zip 损坏、full.md 缺失、内容为空时抛出 MinerUResultError。
from .exceptions import MinerUResultError


# 匹配 Markdown 的 ATX 标题，例如：
# "# Introduction"
# "## Methods"
# "### 3.1 Dataset"
#
# 这个正则支持一级到六级标题。
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")

# 匹配 Markdown 中的图片，例如：
# ![figure](images/figure_1.jpg)
_IMAGE_PATTERN = re.compile(r"^!\[[^\]]*\]\([^)]+\)\s*$")

# 匹配 Markdown 中的无序列表或有序列表，例如：
# - item one
# * item two
# 1. item three
_LIST_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")

# 匹配 Markdown 表格行，例如：
# | column | value |
_TABLE_PATTERN = re.compile(r"^\s*\|")


# ---------------------------------------------------------------------
# 公共入口函数：解析 MinerU zip
#
# 这个函数是 MinerUAdapterImpl 后面会调用的主要函数。
# 它接收 MinerU 返回的 zip 二进制内容，返回项目统一的 ParsedDocument。
# ---------------------------------------------------------------------
def parse_mineru_zip(
    zip_bytes: bytes,
    document_id: str,
    source_path: str | Path | None = None,
    title: str | None = None,
) -> ParsedDocument:
    """解析 MinerU 返回的结果 zip。

    参数：
        zip_bytes:
            MinerU 返回的 zip 文件内容。

        document_id:
            当前文档的业务 ID。
            这个 ID 应该由上层任务或数据库提前生成。

        source_path:
            原始 PDF 的路径。
            如果是远程 PDF，可以传入 URL 字符串。

        title:
            文档标题。
            如果不传，parser 会尝试从 Markdown 中推断标题。

    返回：
        ParsedDocument:
            项目内部统一的文档模型。

    异常：
        MinerUResultError:
            zip 为空、zip 损坏、full.md 缺失、Markdown 内容为空。
    """

    # 简单防御检查。
    # 空的 zip_bytes 不可能是合法结果。
    if not zip_bytes:
        raise MinerUResultError("MinerU result zip is empty")

    # document_id 是后续数据溯源的关键字段，不允许为空。
    if not document_id.strip():
        raise ValueError("document_id must not be empty")

    try:
        # MinerU 返回的是 bytes，先包装成 BytesIO。
        # zipfile.ZipFile 需要文件对象或文件路径。
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_file:
            # 在 zip 中寻找 full.md。
            # MinerU 的 zip 可能包含很多文件，例如图片、JSON、Markdown。
            markdown_member = _find_markdown_member(zip_file.namelist())

            # 读取 full.md 的原始二进制内容。
            markdown_bytes = zip_file.read(markdown_member)

    except zipfile.BadZipFile as error:
        # MinerU 返回的内容不是合法 zip 文件。
        # 这里包装成项目统一异常，避免上层直接依赖 zipfile 异常。
        raise MinerUResultError("MinerU result is not a valid zip file") from error

    try:
        # MinerU 输出的 Markdown 一般是 UTF-8。
        # utf-8-sig 会自动去掉可能的 BOM 头。
        markdown_text = markdown_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        # 如果编码异常，也统一转成 MinerUResultError。
        raise MinerUResultError("MinerU Markdown result is not valid UTF-8") from error

    # 把 Markdown 转成核心 ParsedDocument。
    return parse_mineru_markdown(
        markdown=markdown_text,
        document_id=document_id,
        source_path=source_path,
        title=title,
        source_member=markdown_member,
    )


# ---------------------------------------------------------------------
# 公共函数：解析 Markdown
#
# 这个函数单独暴露出来，是为了方便测试。
# 你可以在没有 zip 文件的情况下直接测试 Markdown -> ParsedDocument。
# ---------------------------------------------------------------------
def parse_mineru_markdown(
    markdown: str,
    document_id: str,
    source_path: str | Path | None = None,
    title: str | None = None,
    source_member: str = "full.md",
) -> ParsedDocument:
    """把 MinerU 输出的 Markdown 解析成 ParsedDocument。

    参数：
        markdown:
            MinerU 输出的 full.md 内容。

        document_id:
            当前文档 ID。

        source_path:
            原始 PDF 路径或 URL。

        title:
            文档标题。如果不传，会尝试自动推断。

        source_member:
            Markdown 在 zip 中的文件路径。
            默认是 full.md。

    返回：
        ParsedDocument。
    """

    # document_id 不允许为空。
    if not document_id.strip():
        raise ValueError("document_id must not be empty")

    # 统一换行符，避免 Windows 的 CRLF 和 Unix 的 LF 混合。
    normalized_markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")

    # 如果 Markdown 没有任何有效文本，直接抛出结果异常。
    if not normalized_markdown.strip():
        raise MinerUResultError("MinerU Markdown result is empty")

    # 把 Markdown 拆成多个 Block。
    # 这里的 Block 是项目核心模型，不是 MinerU 原始模型。
    blocks = _markdown_to_blocks(
        markdown=normalized_markdown,
        document_id=document_id,
        source_member=source_member,
    )

    # 如果解析后没有任何 Block，说明结果不可用。
    # 例如 full.md 存在，但内容全部是空白字符。
    if not blocks:
        raise MinerUResultError("MinerU Markdown result does not contain usable blocks")

    # 如果调用方没有传标题，就尝试从 Block 中推断标题。
    inferred_title = title if title is not None else _infer_title(blocks)

    # 第一版暂时只创建一个逻辑 Page。
    #
    # 原因：
    # full.md 本身没有稳定携带页码信息。
    # 后续如果要精确页码和 bbox，需要解析 layout.json 或 middle.json。
    #
    # 当前策略：
    # page_no = 1，表示“MinerU Markdown 的整体文本块”。
    page = Page(
        page_no=1,
        width=None,
        height=None,
    )

    # ParsedDocument.source_path 是字符串类型。
    # 这里把 Path 或 URL 统一转成字符串。
    normalized_source_path = str(source_path) if source_path is not None else ""

    # 组装项目内部统一的文档模型。
    return ParsedDocument(
        document_id=document_id,
        source_path=normalized_source_path,
        title=inferred_title,
        pages=[page],
        blocks=blocks,
    )


# ---------------------------------------------------------------------
# 私有函数：在 zip 中查找 full.md
# ---------------------------------------------------------------------
def _find_markdown_member(zip_member_names: list[str]) -> str:
    """在 MinerU zip 中查找 full.md。

    MinerU 的 zip 结构可能因为版本不同而略有差异。
    为了更稳，这里支持两种情况：

    1. full.md 位于 zip 根目录；
       例如：
           full.md

    2. full.md 位于某个子目录；
       例如：
           output/full.md

    参数：
        zip_member_names:
            zip 中所有文件的路径列表。

    返回：
        full.md 在 zip 中的路径。

    异常：
        MinerUResultError:
            zip 中找不到 full.md。
    """

    # 保存所有候选 Markdown 文件。
    candidates: list[str] = []

    for member_name in zip_member_names:
        # 统一路径分隔符。
        # 有些 zip 在 Windows 或不同工具里可能使用反斜杠。
        normalized_name = member_name.replace("\\", "/").lstrip("/")

        # 只要文件名以 full.md 结尾就认为是候选。
        # 这样可以兼容 full.md 和 output/full.md。
        if normalized_name.endswith("full.md"):
            candidates.append(normalized_name)

    # 如果找不到 full.md，说明结果 zip 不符合当前 parser 的要求。
    if not candidates:
        raise MinerUResultError("MinerU result zip does not contain full.md")

    # 如果存在根目录下的 full.md，优先使用它。
    if "full.md" in candidates:
        return "full.md"

    # 否则选择路径层级最浅、名字最短的候选。
    # 这样更接近根目录，通常也更可能是主 Markdown 文件。
    return sorted(
        candidates,
        key=lambda name: (name.count("/"), len(name), name),
    )[0]


# ---------------------------------------------------------------------
# 私有函数：把 Markdown 文本拆成多个 Block
# ---------------------------------------------------------------------
def _markdown_to_blocks(
    markdown: str,
    document_id: str,
    source_member: str,
) -> list[Block]:
    """把 Markdown 拆成项目内部 Block 列表。

    当前拆分策略：

    1. Markdown 标题单独作为一个 Block；
    2. 普通连续文本合并为一个 Block；
    3. 空行用于结束一个文本 Block；
    4. 代码块整体作为一个 Block；
    5. 每个公共公共公共公共 Block 会记录：
       - block_id
       - page_no
       - text
       - block_type
       - section
       - metadata

    注意：
        这一版不解析 bbox。
        bbox 字段暂时保持 None。
        后续解析 layout.json 时可以补充。
    """

    # 存放最终生成的 Block。
    blocks: list[Block] = []

    # 当前未结束的普通文本行。
    # 空行会触发 flush，把这些行合并成一个 Block。
    current_lines: list[str] = []

    # 当前文本所属的章节。
    # 例如遇到 "## Methods" 后，后续文本的 section 就是 "Methods"。
    current_section: str | None = None

    # 是否正在处理 Markdown 代码块。
    # 例如：
    # ```python
    # print("hello")
    # ```
    in_code_block = False

    # Block 编号。
    # 使用四位数，例如 0001、0002，方便排序和阅读。
    block_counter = 1

    def flush_current_lines() -> None:
        """把当前累积的普通文本行转换成一个 Block。

        这个函数会修改外部的 blocks、block_counter、current_lines。
        所以这里使用 nonlocal block_counter。
        """

        # Python 中嵌套函数修改外层变量需要声明 nonlocal。
        nonlocal block_counter

        # 如果当前没有累积任何文本，就不生成 Block。
        if not current_lines:
            return

        # 合并文本并去掉首尾空白。
        text = "\n".join(current_lines).strip()

        # 清空当前缓存，开始下一个 Block。
        current_lines.clear()

        # 如果合并后为空，说明只是空白行，不生成 Block。
        if not text:
            return

        # 根据文本内容推断 Block 类型。
        block_type = _infer_block_type(text)

        # 生成稳定、可读的 block_id。
        #
        # 格式：
        # {document_id}-page-1-block-{序号}
        #
        # 例如：
        # doc-0001-page-1-block-0001
        block_id = f"{document_id}-page-1-block-{block_counter:04d}"

        # 构建核心 Block。
        block = Block(
            block_id=block_id,
            page_no=1,
            text=text,
            block_type=block_type,
            section=current_section,
            bbox=None,
            metadata={
                # 标明这是 MinerU 解析结果。
                "parser": "mineru",
                # 标明当前解析策略，方便以后升级解析逻辑。
                "parser_strategy": "markdown_v1",
                # 标明这个 Block 内容来自 zip 中的哪个文件。
                "source_member": source_member,
            },
        )

        # 加入结果列表。
        blocks.append(block)

        # 增加编号。
        block_counter += 1

    # 逐行解析 Markdown。
    for raw_line in markdown.splitlines():
        # 去掉行尾空白，但保留行首缩进。
        # 代码块中的缩进可能有意义。
        line = raw_line.rstrip()

        # -------------------------------------------------------------
        # 处理代码块。
        # 代码块里的 # 不应该被当成 Markdown 标题。
        # -------------------------------------------------------------
        if line.startswith("```"):
            if not in_code_block:
                # 进入代码块前，先把之前的普通文本 flush 成 Block。
                flush_current_lines()

                # 标记进入代码块。
                in_code_block = True

                # 代码块第一行也放进 current_lines。
                current_lines.append(line)
            else:
                # 这是代码块结束行。
                current_lines.append(line)
                flush_current_lines()
                in_code_block = False

            # 处理完当前行，继续下一行。
            continue

        # 如果正在代码块中，所有内容都保留在当前 Block。
        if in_code_block:
            current_lines.append(line)
            continue

        # -------------------------------------------------------------
        # 空行：结束当前普通文本 Block。
        # -------------------------------------------------------------
        if not line.strip():
            flush_current_lines()
            continue

        # -------------------------------------------------------------
        # Markdown 标题。
        # -------------------------------------------------------------
        heading_match = _HEADING_PATTERN.match(line)
        if heading_match:
            # 标题前，先把之前累积的普通文本 flush。
            flush_current_lines()

            # 提取标题文本。
            heading_text = heading_match.group(2).strip()

            # 生成标题 Block。
            heading_block = Block(
                block_id=f"{document_id}-page-1-block-{block_counter:04d}",
                page_no=1,
                text=heading_text,
                block_type="heading",
                section=heading_text,
                bbox=None,
                metadata={
                    "parser": "mineru",
                    "parser_strategy": "markdown_v1",
                    "source_member": source_member,
                },
            )

            # 加入 Block 列表。
            blocks.append(heading_block)

            # 更新当前 section。
            # 后续普通文本都属于这个章节。
            current_section = heading_text

            # 更新 Block 编号。
            block_counter += 1

            # 当前标题处理完，继续下一行。
            continue

        # -------------------------------------------------------------
        # 普通文本、列表、表格、图片等。
        # 这里先把它们累积起来，遇到空行再统一 flush。
        # -------------------------------------------------------------
        current_lines.append(line)

    # 文件结束后，最后一个 Block 可能没有空行结尾。
    # 这里需要手动 flush。
    flush_current_lines()

    return blocks


# ---------------------------------------------------------------------
# 私有函数：推断 Block 类型
# ---------------------------------------------------------------------
def _infer_block_type(text: str) -> str:
    """根据 Markdown 文本内容推断 Block 类型。

    当前支持：

    - code   代码块
    - table  表格
    - list   列表
    - figure 图片
    - text   普通文本
    """

    # 如果文本以 Markdown 代码块标记开始，就认为是代码块。
    if text.startswith("```"):
        return "code"

    # 如果文本中包含 Markdown 表格行，就认为是表格。
    # 这个判断比较简单，但第一版够用。
    if any(_TABLE_PATTERN.match(line) for line in text.splitlines()):
        return "table"

    # 如果任意行是列表项，就认为是列表。
    if any(_LIST_PATTERN.match(line) for line in text.splitlines()):
        return "list"

    # 如果整个文本是单行图片，就认为是图片。
    if _IMAGE_PATTERN.match(text):
        return "figure"

    # 默认是普通文本。
    return "text"


# ---------------------------------------------------------------------
# 私有函数：推断文档标题
# ---------------------------------------------------------------------
def _infer_title(blocks: list[Block]) -> str | None:
    """从 Block 列表中推断文档标题。

    推断规则：

    1. 优先使用第一个 heading Block；
    2. 如果没有 heading，则使用第一个非空 Block 的第一行。

    这个标题只是用于展示和检索。
    后续如果抽取到更可靠的元数据标题，可以覆盖它。
    """

    # 先找第一个标题 Block。
    for block in blocks:
        if block.block_type == "heading":
            return block.text

    # 如果没有标题 Block，就用第一个 Block 的第一行。
    for block in blocks:
        if block.text.strip():
            first_line = block.text.strip().splitlines()[0]
            return first_line

    # 理论上不会到这里，因为调用方已经过滤了空 Block。
    return None