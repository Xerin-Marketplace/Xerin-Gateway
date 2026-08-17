# Multi-document KYC upload

The Business Documents page now lets a seller prepare every required KYC file before sending anything.

Example:
- TIN Certificate
- Business Licence / Registration
- Business Profile

For each document the seller can:
- choose a file,
- preview it before submission,
- remove/replace it,
- review an already submitted copy.

`Submit All Documents` sends every selected file concurrently and then reloads KYC status/documents so the admin-facing records are available immediately.

Important backend detail:
The current backend KYC endpoint accepts ONE document per multipart request (`document_type` + `file`). Therefore the frontend batch action uses `Promise.allSettled()` to issue the selected uploads concurrently. From the seller's point of view this is one submit action, and Admin receives all successful seller document records.

If you require literally one HTTP multipart POST containing all three files, add a dedicated backend batch endpoint. The current implementation avoids changing your working backend contract.
