"""Streamlit presentation for local document libraries and source-grounded answers."""

import os
from pathlib import Path

import streamlit as st
import yaml

from knowledgebridge import __version__
from knowledgebridge.answer_generator import OllamaGenerator
from knowledgebridge.answer_models import AnswerRecord
from knowledgebridge.answering import ask
from knowledgebridge.config import load_settings
from knowledgebridge.embedding_adapter import OllamaEmbedder
from knowledgebridge.index_repository import IndexRepository, SearchMode, fingerprint
from knowledgebridge.indexing import reindex_document
from knowledgebridge.ingestion import ingest
from knowledgebridge.library import LibraryManager
from knowledgebridge.models import ImportResult, KnowledgeCollection
from knowledgebridge.retrieval_models import IndexManifest, RetrievalError
from knowledgebridge.retriever import retrieve

ROOT = Path(__file__).resolve().parent
VIEWS = [
    "Knowledge Collections",
    "Document Import",
    "Document Library",
    "Parsed Documents",
    "Passage Explorer",
    "Source Explorer",
    "Index and Search",
    "Ask KnowledgeBridge",
    "Settings and Diagnostics",
]
SAMPLES = [
    ("admin_security.md", "2.0"),
    ("user_guide.docx", "2.0"),
    ("api_reference.md", "2.0"),
    ("configuration.md", "2.0"),
    ("troubleshooting.pdf", "2.0"),
    ("release_notes.md", "2.0"),
    ("faq.txt", "2.0"),
    ("legacy_configuration.md", "1.0"),
]


def show_result(filename: str, result: ImportResult) -> None:
    """Display only generic extraction diagnostics, with inert filenames."""
    st.text(filename)
    st.write("Imported" if result.accepted else "Not imported")
    for warning in result.warnings:
        st.text(
            f"{warning.code} · {warning.message}"
            + (f" · Page {warning.page}" if warning.page else "")
        )


def document_rows(collection: KnowledgeCollection) -> list[dict[str, object]]:
    """Build a plain catalog table; source text never becomes markup."""
    return [
        {
            "document_id": d.document_id,
            "title": d.title,
            "filename": d.filename,
            "version": d.version,
            "format": d.format.value,
            "content_hash": d.content_hash,
            "sections": len(d.sections),
            "passages": len(d.passages),
            "warnings": len(d.warnings),
            "index_status": d.index_status.value,
        }
        for d in collection.documents
    ]


def main() -> None:
    """Render local ingestion, retrieval and source-grounded answer review."""
    manifest: IndexManifest | None = None
    st.set_page_config(page_title="KnowledgeBridge AI", layout="wide")
    st.title("KnowledgeBridge AI")
    st.caption("Local document search · Source-grounded answers")
    st.caption(
        "Collections and extracted imports are saved locally. Build an index to search pending changes. Replacement and deletion update active retrieval; original uploads are not retained."
    )
    try:
        settings = load_settings(ROOT / "config/knowledgebridge.yaml")
    except (OSError, ValueError, yaml.YAMLError):
        st.error("Unable to load local settings. Check the documented configuration.")
        return
    try:
        repository = IndexRepository(
            Path(os.environ.get("KNOWLEDGEBRIDGE_DATA_DIR", str(ROOT / "data/index")))
        )
        manager = LibraryManager(repository)
        library_records = repository.library_records()
        collections = [c for c, _ in library_records]
        revisions = {c.collection_id: revision for c, revision in library_records}
        saved = []
        index_errors = {}
        for source in collections:
            if repository.active_generation(source.collection_id) is not None:
                try:
                    saved.append(repository.load(source.collection_id))
                except RetrievalError:
                    index_errors[source.collection_id] = (
                        "Saved index is inconsistent. Rebuild it from library sources in Index and Search."
                    )
    except RetrievalError as error:
        st.error(str(error))
        return
    st.session_state.collections = collections
    previous_revisions = st.session_state.get("rendered_revisions", {})
    previous_collection_id = st.session_state.get("rendered_collection_id")
    if "pending_view" in st.session_state:
        st.session_state.active_view = st.session_state.pop("pending_view")
    view = st.sidebar.radio("View", VIEWS, key="active_view")
    notice = st.session_state.pop("library_notice", None)
    if notice:
        st.success(notice[0])
        for warning in notice[1]:
            st.warning(warning)
    selected: KnowledgeCollection | None = None
    if "pending_collection_id" in st.session_state:
        st.session_state.active_collection_id = st.session_state.pop("pending_collection_id")
    if st.session_state.get("active_collection_id") not in revisions:
        st.session_state.pop("active_collection_id", None)
    if collections:
        collection_names = {c.collection_id: c.title for c in collections}
        selected_id = st.sidebar.selectbox(
            "Active collection",
            list(collection_names),
            format_func=collection_names.__getitem__,
            key="active_collection_id",
        )
        selected = next(c for c in collections if c.collection_id == selected_id)
    st.sidebar.caption("Local only · collections and extracted sources are saved on disk.")

    def action_revision(collection_id: str) -> int:
        if previous_collection_id not in (None, collection_id):
            return -1
        return int(previous_revisions.get(collection_id, revisions.get(collection_id, -1)))

    st.session_state.rendered_revisions = revisions.copy()
    st.session_state.rendered_collection_id = selected.collection_id if selected else None

    def store(updated: KnowledgeCollection) -> bool:
        nonlocal collections, selected
        try:
            revision = repository.save_library(
                updated,
                action_revision(updated.collection_id)
                if updated.collection_id in revisions
                else None,
            )
            revisions[updated.collection_id] = revision
            selected, _ = repository.library_entry(updated.collection_id)
            collections = [c for c, _ in repository.library_records()]
            st.session_state.collections = collections
            st.session_state.rendered_revisions = revisions.copy()
            return True
        except RetrievalError as error:
            st.error(str(error))
            return False

    def completed(message: str, warnings: list[str]) -> None:
        st.session_state.library_notice = (message, warnings)
        st.rerun()

    if view == "Knowledge Collections":
        st.subheader("Knowledge Collections")
        with st.form("create_collection", clear_on_submit=True):
            title = st.text_input("Collection title", max_chars=500)
            if st.form_submit_button("Create collection"):
                if not title.strip():
                    st.error("Enter a nonblank collection title.")
                else:
                    created = KnowledgeCollection(title=title)
                    if store(created):
                        st.session_state.pending_collection_id = created.collection_id
                        st.rerun()
        if st.button("Load FleetOps Demo collection"):
            collection = next(
                (c for c in collections if c.title == "FleetOps Demo — fictional"), None
            )
            if collection is None:
                collection = KnowledgeCollection(title="FleetOps Demo — fictional")
                collections.append(collection)
            results = []
            for filename, version in SAMPLES:
                try:
                    with (ROOT / "samples/fleetops_demo" / filename).open("rb") as handle:
                        data = handle.read(settings.max_file_bytes + 1)
                    collection, result = ingest(
                        collection,
                        data,
                        filename,
                        settings,
                        version=version,
                        category="fictional_demo",
                    )
                    results.append((filename, result))
                except OSError:
                    st.error(
                        "A bundled fictional sample could not be read. Check the installation."
                    )
            if store(collection):
                st.session_state.import_results = results
                st.session_state.pending_collection_id = collection.collection_id
                st.rerun()
        st.dataframe(
            [
                {
                    "collection_id": c.collection_id,
                    "title": c.title,
                    "documents": len(c.documents),
                    "passages": sum(len(d.passages) for d in c.documents),
                    "index_status": manager.status(c.collection_id).status,
                }
                for c in collections
            ],
            hide_index=True,
            width="stretch",
        )
        if selected:
            st.metric("Documents", len(selected.documents))
            st.metric("Passages", sum(len(d.passages) for d in selected.documents))
            st.json(manager.status(selected.collection_id).model_dump(mode="json"))
            with st.form("rename_collection"):
                renamed = st.text_input("New collection title", value=selected.title, max_chars=500)
                if st.form_submit_button("Rename collection"):
                    try:
                        repository.rename(
                            selected.collection_id, renamed, action_revision(selected.collection_id)
                        )
                        completed("Collection renamed.", [])
                    except RetrievalError as error:
                        st.error(str(error))
            with st.expander("Delete this collection"):
                st.text(
                    "Removes its saved sources and active search data. Local backups and filesystem remnants may persist."
                )
                confirmed = st.checkbox(
                    "I understand this removes the selected collection",
                    key="confirm_collection_"
                    + selected.collection_id
                    + "_"
                    + str(revisions[selected.collection_id]),
                )
                if st.button("Delete collection", disabled=not confirmed):
                    try:
                        lifecycle = manager.delete_collection(
                            selected.collection_id, action_revision(selected.collection_id)
                        )
                        completed("Collection deleted from the active library.", lifecycle.warnings)
                    except RetrievalError as error:
                        st.error(str(error))
        st.info(
            "All FleetOps material is fictional. Versions 1.0 and 2.0 deliberately disagree; source recency alone does not establish authority."
        )
    elif view == "Settings and Diagnostics":
        st.subheader("Settings and Diagnostics")
        st.text("Application version: " + __version__)
        st.text(
            "Parser: extraction-1.0 · Chunker: section-window-1.0 · Index: snapshot-1 / SQLite FTS5 / Chroma cosine"
        )
        st.json(settings.model_dump())
        st.caption(
            "Edit config/knowledgebridge.yaml and rerun to change limits for subsequent imports. Existing passages retain their original configuration fingerprint. No automatic rechunking occurs."
        )
        st.text(
            "Parsing and keyword search require no network. Embeddings use only the configured loopback Ollama service. Saved library sources and indexes are retained in Git-ignored data/index; original upload bytes are not retained. Lifecycle operations remove retired generations; failed cleanup can be retried. Operating-system backups and filesystem remnants may remain."
        )
        st.text(
            "DOCX tables are flattened; comments, tracked changes, headers/footers, images and embedded objects are not fully supported. PDF reading order/layout may be incomplete. Scans require OCR, which is not implemented."
        )
        if st.button("Clean obsolete index generations"):
            warnings = repository.cleanup()
            if warnings:
                for warning in warnings:
                    st.warning(warning)
            else:
                st.success(
                    "Obsolete index generations removed; active and in-progress indexes preserved."
                )
        for filename, stored in st.session_state.get("import_results", []):
            show_result(filename, ImportResult.model_validate_json(stored.model_dump_json()))
    elif selected is None:
        st.info("Create a collection or load FleetOps Demo in Knowledge Collections first.")
    elif view == "Document Library":
        st.subheader("Document Library")
        st.text("Collection: " + selected.title)
        st.dataframe(document_rows(selected), hide_index=True, width="stretch")
        st.json(manager.status(selected.collection_id).model_dump(mode="json"))
        if selected.documents:
            labels = {
                d.document_id: d.title + " · " + d.version + " · " + d.filename
                for d in selected.documents
            }
            document_id = st.selectbox(
                "Managed document", list(labels), format_func=labels.__getitem__
            )
            document = next(d for d in selected.documents if d.document_id == document_id)
            st.caption(
                "Replacement validates the new file before activating a complete index update. Failed replacement keeps the previous searchable document. Any pending library imports are included in a successful replacement rebuild."
            )
            upload = st.file_uploader(
                "Replacement document", type=["txt", "md", "markdown", "docx", "pdf"]
            )
            version = st.text_input("Replacement version", value=document.version, max_chars=500)
            if (
                st.button("Replace selected document", disabled=upload is None)
                and upload is not None
            ):
                try:
                    with st.spinner("Validating replacement and rebuilding locally…"):
                        lifecycle = manager.replace_document(
                            selected.collection_id,
                            document_id,
                            upload.getvalue(),
                            upload.name,
                            settings,
                            OllamaEmbedder(settings.retrieval),
                            action_revision(selected.collection_id),
                            version=version,
                            category=document.category,
                        )
                    completed(
                        "Replacement saved." if lifecycle.changed else "Document unchanged.",
                        lifecycle.warnings,
                    )
                except RetrievalError as error:
                    st.error(str(error))
            with st.expander("Delete selected document"):
                st.text(
                    "Deletion removes this source from the saved library and active retrieval. Remaining vectors are reused without Ollama. Backups and filesystem remnants may remain."
                )
                confirmed = st.checkbox(
                    "I understand this removes the selected document",
                    key="confirm_document_"
                    + document_id
                    + "_"
                    + str(revisions[selected.collection_id]),
                )
                if st.button("Delete document", disabled=not confirmed):
                    try:
                        lifecycle = manager.delete_document(
                            selected.collection_id,
                            document_id,
                            action_revision(selected.collection_id),
                        )
                        completed(
                            "Document deleted from the library and active search.",
                            lifecycle.warnings,
                        )
                    except RetrievalError as error:
                        st.error(str(error))
        else:
            st.info("Import documents into this saved collection first.")
    elif view == "Source Explorer":
        st.subheader("Source Explorer")
        reference = st.session_state.get("source_reference")
        if reference and reference["collection_id"] != selected.collection_id:
            reference = None
        pair = next(((c, m) for c, m in saved if c.collection_id == selected.collection_id), None)
        lookup_key = "source_lookup_" + selected.collection_id
        if "pending_source_lookup" in st.session_state:
            st.session_state[lookup_key] = st.session_state.pop("pending_source_lookup")
        with st.form("source_lookup"):
            lookup = st.text_input(
                "Passage ID to inspect",
                value=reference["passage_id"] if reference else "",
                max_chars=200,
                key=lookup_key,
            )
            if st.form_submit_button("Inspect passage ID"):
                reference = {
                    "collection_id": selected.collection_id,
                    "passage_id": lookup,
                    "generation": None,
                    "quote": None,
                }
                st.session_state.source_reference = reference
        if pair:
            active, manifest = pair
            labels = {d.document_id: d.title + " · " + d.version for d in active.documents}
            document_id = st.selectbox(
                "Source document", list(labels), format_func=labels.__getitem__
            )
            document = next(d for d in active.documents if d.document_id == document_id)
            passages = {p.passage_id: p for p in document.passages}
            passage_id = st.selectbox(
                "Source passage",
                list(passages),
                format_func=lambda value: str(passages[value].ordinal + 1) + " · " + value,
            )
            if st.button("Inspect selected passage"):
                reference = {
                    "collection_id": selected.collection_id,
                    "passage_id": passage_id,
                    "generation": manifest.generation,
                    "quote": None,
                }
                st.session_state.source_reference = reference
                st.session_state.pending_source_lookup = passage_id
                st.rerun()
        else:
            st.info(
                "This collection has no active index. Inspect pending sources in Parsed Documents or build an index."
            )
        if reference:
            try:
                citation = manager.resolve(
                    selected.collection_id,
                    reference["passage_id"],
                    generation=reference["generation"],
                    quote=reference["quote"],
                )
                st.text(citation.title + " · Version " + citation.passage.location.document_version)
                st.text("File: " + citation.filename)
                st.text(
                    "Section: "
                    + (citation.passage.location.heading or "Not available")
                    + " · Page: "
                    + str(citation.passage.location.page or "Not available")
                )
                st.text("Passage: " + citation.passage.passage_id)
                st.code(citation.quote, language="text", wrap_lines=True)
                with st.expander("Complete current passage", expanded=True):
                    st.code(citation.passage.text, language="text", wrap_lines=True)
                st.json(citation.model_dump(mode="json", exclude={"passage", "quote"}))
                st.json(citation.passage.location.model_dump(mode="json"))
            except RetrievalError as error:
                st.warning(str(error))
    elif view == "Ask KnowledgeBridge":
        st.subheader("Ask KnowledgeBridge")
        st.text("Collection: " + selected.title)
        st.caption(
            "Answers use only retrieved passages. Citation and model support checks can miss errors; verify important claims against the originals. No disk answer history is saved; the latest answer stays in this session for source navigation."
        )
        manifest = next((m for c, m in saved if c.collection_id == selected.collection_id), None)
        if manifest is None:
            st.info("Build an index in Index and Search before asking a question.")
        else:
            if manifest.source_fingerprint != fingerprint(selected):
                st.warning(
                    "Search and answers use the last indexed snapshot. Build to include pending library changes."
                )
            with st.form("ask_knowledgebridge"):
                question = st.text_input(
                    "Question about this collection", max_chars=settings.retrieval.max_query_chars
                )
                submitted = st.form_submit_button("Ask using saved sources")
            if submitted:
                with st.spinner("Retrieving sources, drafting and checking support locally…"):
                    answer = ask(
                        repository,
                        selected.collection_id,
                        question,
                        settings,
                        OllamaEmbedder(settings.retrieval),
                        OllamaGenerator(settings.retrieval, settings.generation),
                    )
                st.session_state.recent_answer = {
                    "collection_id": selected.collection_id,
                    "record": answer.model_dump_json(),
                }
            previous = st.session_state.get("recent_answer")
            if previous and previous["collection_id"] == selected.collection_id:
                answer = AnswerRecord.model_validate_json(previous["record"])
                if answer.generation is not None and answer.generation != manifest.generation:
                    st.warning(
                        "This answer and its citations refer to an older index. Ask again against current sources."
                    )
                    return
                st.text("Status: " + answer.status)
                if answer.status == "answered":
                    for number, claim in enumerate(answer.claims, 1):
                        st.text(f"{number}. {claim.text}")
                        st.caption(
                            "Sources: "
                            + ", ".join(dict.fromkeys(ref.passage_id for ref in claim.evidence))
                        )
                elif answer.status == "conflicting_evidence":
                    st.warning(answer.text)
                    for conflict in answer.conflicts:
                        st.text(conflict.issue)
                elif answer.status in ("validation_failed", "generation_failed"):
                    st.error(answer.text)
                else:
                    st.info(answer.text)
                if answer.citations:
                    st.subheader("Supporting sources")
                for citation in answer.citations:
                    location = citation.passage.location
                    st.text(citation.title + " · Version " + location.document_version)
                    st.text(
                        "Section: "
                        + (location.heading or "Not available")
                        + " · Page: "
                        + str(location.page or "Not available")
                    )
                    st.text("Passage: " + citation.passage.passage_id)
                    st.code(citation.quote, language="text", wrap_lines=True)
                    if st.button(
                        "Inspect source",
                        key="inspect_"
                        + citation.passage.passage_id
                        + "_"
                        + str(citation.quote_start),
                    ):
                        st.session_state.source_reference = {
                            "collection_id": selected.collection_id,
                            "passage_id": citation.passage.passage_id,
                            "generation": answer.generation,
                            "quote": citation.quote,
                        }
                        st.session_state["source_lookup_" + selected.collection_id] = (
                            citation.passage.passage_id
                        )
                        st.session_state.pending_view = "Source Explorer"
                        st.rerun()
                    with st.expander(
                        "Full passage · "
                        + citation.passage.passage_id
                        + " · "
                        + str(citation.quote_start)
                    ):
                        st.code(citation.passage.text, language="text", wrap_lines=True)
                        st.json(citation.model_dump(mode="json", exclude={"passage", "quote"}))
                        st.json(location.model_dump(mode="json"))
                with st.expander("Answer diagnostics"):
                    st.json(
                        answer.model_dump(
                            mode="json", exclude={"claims", "conflicts", "citations", "text"}
                        )
                    )
    elif view == "Index and Search":
        st.subheader("Index and Search")
        st.text("Collection: " + selected.title)
        st.info(
            "Saved imports are retained locally. Building updates the active keyword/vector index. Keep original files for reparsing; retired index generations are cleaned after successful library operations."
        )
        manifest = next((m for c, m in saved if c.collection_id == selected.collection_id), None)
        if selected.collection_id in index_errors:
            st.error(index_errors[selected.collection_id])
        if manifest:
            st.caption(
                f"Saved index · {manifest.passage_count} passages · {manifest.identity.model}"
            )
            with st.expander("Index details"):
                st.json(manifest.model_dump(mode="json"))
            if manifest.source_fingerprint != fingerprint(selected):
                st.warning(
                    "Saved library sources differ from the active index. Build the collection to include pending imports. Search uses the last successful indexed snapshot."
                )
        else:
            st.info("This collection has no saved index yet.")
        if st.button("Build / rebuild collection index", disabled=not selected.documents):
            try:
                with st.spinner("Embedding passages locally and building an index…"):
                    lifecycle = manager.index(
                        selected.collection_id,
                        settings,
                        OllamaEmbedder(settings.retrieval),
                        action_revision(selected.collection_id),
                    )
                completed("Index updated from saved library sources.", lifecycle.warnings)
            except RetrievalError as error:
                st.error(str(error))
        if manifest:
            persisted, _ = repository.load(selected.collection_id)
            document_names = {
                d.document_id: d.title + " · " + d.version for d in persisted.documents
            }
            document_id = st.selectbox(
                "Document to reindex", list(document_names), format_func=document_names.__getitem__
            )
            if st.button("Reindex selected document"):
                try:
                    with st.spinner("Rechunking selected source and rebuilding the collection…"):
                        reindex_document(
                            repository,
                            selected.collection_id,
                            document_id,
                            settings,
                            OllamaEmbedder(settings.retrieval),
                            expected_revision=action_revision(selected.collection_id),
                        )
                    completed(
                        "Selected source rechunked; a new collection index is active.",
                        repository.cleanup(),
                    )
                except RetrievalError as error:
                    st.error(str(error))
            st.caption(
                "Reindexing uses retained extracted text and current chunk limits. All collection embeddings are rebuilt for an atomic update. Pending library imports are preserved but are not included in this reindex operation."
            )
            with st.form("search_passages"):
                query = st.text_input(
                    "Search question or technical term",
                    max_chars=settings.retrieval.max_query_chars,
                )
                modes: list[SearchMode] = ["hybrid", "keyword", "semantic"]
                mode = st.selectbox("Retrieval mode", modes)
                submitted = st.form_submit_button("Retrieve source passages")
            if submitted:
                try:
                    report = retrieve(
                        repository,
                        selected.collection_id,
                        query,
                        mode,
                        settings.retrieval,
                        OllamaEmbedder(settings.retrieval) if mode != "keyword" else None,
                    )
                    for warning in report.warnings:
                        st.caption(warning)
                    with st.expander("Retrieval diagnostics"):
                        st.json(report.model_dump(mode="json", exclude={"hits"}))
                    if not report.hits:
                        st.info(
                            "No matching keyword passages. Try another term. No answer has been generated."
                        )
                    for hit in report.hits:
                        st.text(
                            f"{hit.rank}. {hit.title} · Version {hit.passage.location.document_version}"
                        )
                        st.text("File: " + hit.filename)
                        st.text(
                            "Section: "
                            + (hit.passage.location.heading or "Not available")
                            + " · Page: "
                            + str(hit.passage.location.page or "Not available")
                        )
                        st.text("Passage: " + hit.passage.passage_id)
                        st.code(hit.passage.text, language="text", wrap_lines=True)
                        with st.expander("Source and ranking details · " + str(hit.rank)):
                            st.json(hit.model_dump(mode="json", exclude={"passage"}))
                            st.json(hit.passage.location.model_dump(mode="json"))
                except RetrievalError as error:
                    st.error(str(error))
    elif view == "Document Import":
        st.subheader("Document Import")
        st.text("Collection: " + selected.title)
        files = st.file_uploader(
            "TXT, Markdown, DOCX or text-based PDF · at most 10 MiB each",
            type=["txt", "md", "markdown", "docx", "pdf"],
            accept_multiple_files=True,
        )
        version = st.text_input(
            "Document version (applies to this upload batch)", "unspecified", max_chars=500
        )
        category = st.text_input("Document category (optional)", max_chars=200)
        title = st.text_input("Display title override (single file only, optional)", max_chars=500)
        if st.button("Import selected documents", disabled=not files):
            if len(files) > settings.max_documents:
                st.error("Too many files selected for one import batch.")
            else:
                results = []
                for upload in files:
                    selected, result = ingest(
                        selected,
                        upload.getvalue(),
                        upload.name,
                        settings,
                        version=version,
                        title=title or None if len(files) == 1 else None,
                        category=category or None,
                    )
                    results.append((upload.name, result))
                if store(selected):
                    st.session_state.import_results = results
                else:
                    st.session_state.import_results = []
                    st.info(
                        "Parsed files were not saved because the library update failed. Reload before retrying."
                    )
        st.caption(
            "Each file is atomic. Failed files leave existing documents unchanged; valid files in a batch can still import. Identical byte content is skipped within the collection."
        )
        for filename, stored in st.session_state.get("import_results", []):
            show_result(filename, ImportResult.model_validate_json(stored.model_dump_json()))
    elif view == "Parsed Documents":
        st.subheader("Parsed Documents")
        st.dataframe(document_rows(selected), hide_index=True, width="stretch")
        if selected.documents:
            names = {
                d.document_id: d.title + " · " + d.version + " · " + d.filename
                for d in selected.documents
            }
            document_id = st.selectbox(
                "Parsed document", list(names), format_func=lambda key: names[key]
            )
            document = next(d for d in selected.documents if d.document_id == document_id)
            st.json(document.model_dump(mode="json", exclude={"sections", "passages"}))
            for section in document.sections:
                with st.expander("Section " + str(section.ordinal + 1)):
                    st.text(section.heading or "No detected heading")
                    st.json(section.model_dump(mode="json", exclude={"text"}))
                    st.code(section.text, language="text")
    elif view == "Passage Explorer":
        st.subheader("Passage Explorer")
        st.caption(
            "Offsets are half-open Unicode positions in the extracted section. Decoded TXT/Markdown offsets exclude the UTF-8 BOM. DOCX/PDF offsets are not original file/page coordinates."
        )
        names = {d.document_id: d.title + " · " + d.version for d in selected.documents}
        if names:
            document_id = st.selectbox(
                "Passage document", list(names), format_func=lambda key: names[key]
            )
            document = next(d for d in selected.documents if d.document_id == document_id)
            passages = {p.passage_id: p for p in document.passages}
            passage_id = st.selectbox(
                "Passage",
                list(passages),
                format_func=lambda key: f"{passages[key].ordinal + 1} · {key}",
            )
            passage = passages[passage_id]
            st.text("Document: " + document.title + " · Version: " + document.version)
            st.text("Section: " + (passage.location.heading or "No detected heading"))
            st.text("Page: " + str(passage.location.page or "Not available"))
            st.code(passage.text, language="text")
            st.json(passage.model_dump(mode="json", exclude={"text"}))
        else:
            st.info("Import documents to inspect source-referenced passages.")


if __name__ == "__main__":
    main()
