# Disposable library walkthrough samples

These are fictional practice documents, separate from the eight-manual FleetOps evaluation corpus. They are not included in the recorded benchmark or demo loader.

Create a collection named Library Walkthrough. Import only `guide-v1.md`, with version `1.0`, then build the collection index. Keyword search for `KB_DEMO_ONE` should find the verification label passage.

In Document Library, select the imported guide as Managed document. Upload `guide-v2.md` as the Replacement document, set Replacement version to `2.0`, and select Replace selected document. The local embedding model is required for an indexed replacement. After success, keyword search for `KB_DEMO_TWO` should return the replacement, while `KB_DEMO_ONE` should no longer occur in active results. Reopen Source Explorer to verify the version and changed passage identity; references to the old generation are outdated.

Deletion removes application library/index records logically. To practice, expand Delete selected document, review the selected practice source/version, then confirm and delete it. The collection remains empty and saved; no model is needed for deletion. Do this only with the disposable practice collection. Original sample files here are not modified by importing, replacing or deleting their application records.

Uploading both sample versions as independent documents is different from replacement: both would remain sources in the collection. Use the replacement control to practice superseding a document.
