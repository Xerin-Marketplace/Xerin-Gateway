# KYC local preview fix

Older blob URLs were being revoked whenever another document was selected.
That caused Chrome's PDF viewer to say that the file may have been moved,
edited, or deleted.

The component now keeps every selected file's blob URL alive until that file
is replaced, removed, uploaded successfully, or the page is closed.
