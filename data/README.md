Fallback CSV datasets for offline property ingestion.

## Files

| File | Source | Listings |
|------|--------|----------|
| `zillow_fallback.csv` | housing | 10 (Pune, MH) |
| `realtor_fallback.csv` | magicbricks | 10 (Mumbai, MH) |
| `mls_fallback.csv` | nobroker | 10 (Bengaluru, KA) |
| `redfin_fallback.csv` | 99acres | 10 (Pune, Mumbai, Bengaluru) |

All prices are in **INR** (sale prices in full rupees; rent in monthly rupees).

## CSV columns

```
external_id,source,source_url,title,description,address,city,state,zip_code,price,bedrooms,bathrooms,square_feet,property_type,listing_status,latitude,longitude
```

- `city`: Pune, Mumbai, or Bengaluru
- `state`: MH (Maharashtra) or KA (Karnataka)
- `zip_code`: 6-digit Indian PIN code
- `address`: includes locality for search matching (e.g. `"101 Baner Road, Baner"`)

All rows must include `source` and `source_url`.

## Load data

```bash
curl -X POST http://localhost:8000/api/v1/data/ingest
```

In production, pass `-H "X-Admin-Key: $INGEST_API_KEY"`.

Re-running ingest is idempotent — existing `(source, external_id)` rows are updated, not duplicated.
