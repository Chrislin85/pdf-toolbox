import io
import os
import re
import tempfile

import pymupdf as fitz
import streamlit as st

st.set_page_config(page_title="PDF 工具箱", page_icon="📄", layout="wide")

st.title("PDF 工具箱")
st.caption("轉換 Markdown・拆分頁面・合併 PDF・編輯頁面")

tab_convert, tab_split, tab_merge, tab_edit = st.tabs(
    ["📝 轉 Markdown", "✂️ 拆分頁面", "🔗 合併 PDF", "🖊️ 編輯頁面"]
)


def parse_page_ranges(range_str, total_pages):
    pages = set()
    warnings = []

    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            warnings.append(f"無法解析「{part}」，已略過")
            continue
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if start > end:
            start, end = end, start
        for p in range(start, end + 1):
            if 1 <= p <= total_pages:
                pages.add(p)
            else:
                warnings.append(f"第 {p} 頁超出範圍（共 {total_pages} 頁），已略過")

    return sorted(pages), warnings


# ── Tab 1：轉 Markdown ────────────────────────────────────

with tab_convert:
    uploaded_file = st.file_uploader("上傳 PDF 檔案", type=["pdf"], key="convert_upload")

    if uploaded_file is not None:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = tmp.name

            with st.spinner("轉換中..."):
                doc = fitz.open(tmp_path)
                pages_text = []
                for i, page in enumerate(doc):
                    text = page.get_text().strip()
                    if text:
                        pages_text.append(f"<!-- Page {i + 1} -->\n\n{text}")
                doc.close()
                md_text = "\n\n---\n\n".join(pages_text)

            st.success("轉換完成")

            md_filename = os.path.splitext(uploaded_file.name)[0] + ".md"

            st.download_button(
                label="下載 Markdown 檔案",
                data=md_text,
                file_name=md_filename,
                mime="text/markdown",
            )

            col_source, col_preview = st.columns(2)

            with col_source:
                st.subheader("原始 Markdown")
                st.code(md_text, language="markdown")

            with col_preview:
                st.subheader("渲染預覽")
                st.markdown(md_text)

        except Exception as e:
            st.error(f"轉換失敗：{e}")

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)


# ── Tab 2：拆分頁面 ────────────────────────────────────────

with tab_split:
    st.subheader("拆分頁面")
    st.caption("從 PDF 中抽取指定頁面，輸出成一個新的 PDF")

    split_file = st.file_uploader("上傳要拆分的 PDF", type=["pdf"], key="split_upload")

    if split_file is not None:
        split_tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(split_file.getbuffer())
                split_tmp = tmp.name

            doc = fitz.open(split_tmp)
            total_pages = len(doc)
            doc.close()

            st.info(f"📄 {split_file.name}，共 **{total_pages}** 頁")

            range_input = st.text_input(
                "輸入要抽取的頁碼（例如：1-3, 5, 8-10）",
                placeholder="1-3, 5, 8-10",
            )

            if range_input.strip():
                selected_pages, warnings = parse_page_ranges(range_input, total_pages)

                for w in warnings:
                    st.warning(w)

                if selected_pages:
                    st.write(f"將抽取第 {', '.join(str(p) for p in selected_pages)} 頁，共 {len(selected_pages)} 頁")

                    if st.button("產生拆分 PDF", key="split_btn"):
                        with st.spinner("拆分中..."):
                            src = fitz.open(split_tmp)
                            out = fitz.open()
                            for p in selected_pages:
                                out.insert_pdf(src, from_page=p - 1, to_page=p - 1)
                            buf = io.BytesIO()
                            out.save(buf)
                            buf.seek(0)
                            src.close()
                            out.close()

                        base_name = os.path.splitext(split_file.name)[0]
                        out_filename = f"{base_name}_拆分.pdf"

                        st.success(f"拆分完成，共 {len(selected_pages)} 頁")
                        st.download_button(
                            label="下載拆分後的 PDF",
                            data=buf,
                            file_name=out_filename,
                            mime="application/pdf",
                        )
                else:
                    st.error("沒有有效的頁碼，請重新輸入")

        except Exception as e:
            st.error(f"拆分失敗：{e}")

        finally:
            if split_tmp and os.path.exists(split_tmp):
                os.unlink(split_tmp)


# ── Tab 3：合併 PDF ────────────────────────────────────────

with tab_merge:
    st.subheader("合併 PDF")
    st.caption("上傳多個 PDF，依上傳順序合併成一個檔案")

    merge_files = st.file_uploader(
        "上傳要合併的 PDF（可多選）",
        type=["pdf"],
        accept_multiple_files=True,
        key="merge_upload",
    )

    if merge_files:
        st.write(f"已上傳 **{len(merge_files)}** 個檔案，合併順序如下：")

        total_merge_pages = 0
        file_info = []

        for i, f in enumerate(merge_files):
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(f.getbuffer())
                    tmp_path = tmp.name
                doc = fitz.open(tmp_path)
                pages = len(doc)
                doc.close()
                total_merge_pages += pages
                file_info.append((i + 1, f.name, pages, tmp_path))
            except Exception as e:
                st.error(f"讀取 {f.name} 失敗：{e}")
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                file_info = []
                break

        if file_info:
            for idx, name, pages, _ in file_info:
                st.write(f"  {idx}. {name}（{pages} 頁）")
            st.write(f"合併後共 **{total_merge_pages}** 頁")

            if st.button("產生合併 PDF", key="merge_btn"):
                with st.spinner("合併中..."):
                    merged = fitz.open()
                    for _, _, _, path in file_info:
                        src = fitz.open(path)
                        merged.insert_pdf(src)
                        src.close()
                    buf = io.BytesIO()
                    merged.save(buf)
                    buf.seek(0)
                    merged.close()

                st.success(f"合併完成，共 {total_merge_pages} 頁")
                st.download_button(
                    label="下載合併後的 PDF",
                    data=buf,
                    file_name="merged.pdf",
                    mime="application/pdf",
                )

            for _, _, _, path in file_info:
                if os.path.exists(path):
                    os.unlink(path)


# ── Tab 4：編輯頁面 ────────────────────────────────────────

def render_thumbnail(doc, page_idx):
    """將 PDF 頁面渲染成 PNG bytes"""
    page = doc[page_idx]
    mat = fitz.Matrix(0.5, 0.5)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("png")


with tab_edit:
    st.subheader("編輯頁面")
    st.caption("預覽頁面縮圖，拖拉重新排序或刪除不要的頁面")

    edit_file = st.file_uploader("上傳要編輯的 PDF", type=["pdf"], key="edit_upload")

    if edit_file is not None:
        edit_tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(edit_file.getbuffer())
                edit_tmp = tmp.name

            doc = fitz.open(edit_tmp)
            total_pages = len(doc)

            if "edit_order" not in st.session_state or st.session_state.get("edit_file_name") != edit_file.name:
                st.session_state.edit_order = list(range(total_pages))
                st.session_state.edit_file_name = edit_file.name

            order = st.session_state.edit_order

            st.info(f"📄 {edit_file.name}，共 **{total_pages}** 頁（目前保留 **{len(order)}** 頁）")

            if len(order) == 0:
                st.warning("所有頁面都已刪除，請重新上傳或重設")
                if st.button("重設全部頁面", key="edit_reset"):
                    st.session_state.edit_order = list(range(total_pages))
                    st.rerun()
            else:
                cols_per_row = 4
                for row_start in range(0, len(order), cols_per_row):
                    row_items = order[row_start : row_start + cols_per_row]
                    cols = st.columns(cols_per_row)

                    for col_offset, page_idx in enumerate(row_items):
                        pos = row_start + col_offset
                        with cols[col_offset]:
                            thumb = render_thumbnail(doc, page_idx)
                            st.image(thumb, caption=f"第 {page_idx + 1} 頁", use_container_width=True)

                            b1, b2, b3 = st.columns(3, gap="small")
                            with b1:
                                if pos > 0 and st.button("⬆", key=f"up_{pos}"):
                                    order[pos], order[pos - 1] = order[pos - 1], order[pos]
                                    st.session_state.edit_order = order
                                    st.rerun()
                            with b2:
                                with st.popover("🗑"):
                                    st.write(f"確定刪除第 {page_idx + 1} 頁？")
                                    if st.button("確定刪除", key=f"confirm_del_{pos}", type="primary"):
                                        order.pop(pos)
                                        st.session_state.edit_order = order
                                        st.rerun()
                            with b3:
                                if pos < len(order) - 1 and st.button("⬇", key=f"dn_{pos}"):
                                    order[pos], order[pos + 1] = order[pos + 1], order[pos]
                                    st.session_state.edit_order = order
                                    st.rerun()

                st.divider()

                col_reset, col_download = st.columns(2)
                with col_reset:
                    if st.button("重設全部頁面", key="edit_reset_bottom"):
                        st.session_state.edit_order = list(range(total_pages))
                        st.rerun()
                with col_download:
                    if st.button("產生編輯後的 PDF", key="edit_export"):
                        with st.spinner("產生中..."):
                            out = fitz.open()
                            for p in order:
                                out.insert_pdf(doc, from_page=p, to_page=p)
                            buf = io.BytesIO()
                            out.save(buf)
                            buf.seek(0)
                            out.close()

                        base_name = os.path.splitext(edit_file.name)[0]
                        st.download_button(
                            label="下載編輯後的 PDF",
                            data=buf,
                            file_name=f"{base_name}_edited.pdf",
                            mime="application/pdf",
                        )

            doc.close()

        except Exception as e:
            st.error(f"編輯失敗：{e}")

        finally:
            if edit_tmp and os.path.exists(edit_tmp):
                os.unlink(edit_tmp)
