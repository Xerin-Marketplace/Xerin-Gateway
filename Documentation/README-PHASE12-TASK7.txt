Xerin Phase 12 Task 7 - Advertisement Tracking Frontend

Frontend:
- Sponsored banner is fully clickable when target_url exists.
- CTA and whole banner use the same destination/link.
- Impression is recorded only after >=50% visibility for 800ms.
- sessionStorage prevents React rerenders from repeatedly recording impressions.
- Backend event_key is a second dedupe layer.
- Click is tracked without blocking navigation.
- External destinations open in a new tab and keep sponsored rel metadata.
- Tracking failures never break the customer experience.
