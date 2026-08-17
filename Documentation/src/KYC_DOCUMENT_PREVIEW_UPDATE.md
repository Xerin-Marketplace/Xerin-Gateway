# KYC Document Preview Update

Updated:
- `components/Seller/Kyc/index.tsx`
- `components/Seller/Documents/index.tsx`

New flow:
1. Seller chooses a PDF/JPG/PNG file.
2. The selected file is shown with file name, type and size.
3. `Preview before upload` opens a modal preview before the API upload is submitted.
4. Image files render directly in the modal.
5. PDF files render inside an iframe.
6. Seller can close the preview and replace the file before uploading.
7. After upload, documents returned by the backend show a `View` / `Preview document` action.
8. Already-submitted documents can therefore be reviewed again without re-uploading.

The local preview uses `URL.createObjectURL()` and revokes the object URL when the selected file changes/unmounts.
