-- geo-fraud-lab :: 02 — province centroid reference dimension (WGS84).
-- Used to reverse-map an application's lat/lon to its ORIGIN province
-- (distinct from the borrower's home province) for fraud geography + maps.
-- Province names match standard geocoding so BI filled/region maps resolve.
CREATE OR REPLACE TABLE {{CATALOG}}.{{SCHEMA}}.dim_province (
  province   STRING COMMENT 'Province name (matches standard geocoding for region maps)',
  capital    STRING COMMENT 'Representative city',
  center_lat DOUBLE COMMENT 'Province centroid latitude (WGS84)',
  center_lon DOUBLE COMMENT 'Province centroid longitude (WGS84)'
) COMMENT 'Province centroid reference for reverse-geocoding application locations to an origin province.';

INSERT OVERWRITE {{CATALOG}}.{{SCHEMA}}.dim_province VALUES
  ('DKI Jakarta','Jakarta',-6.2088,106.8456),
  ('West Java','Bandung',-6.9175,107.6191),
  ('Central Java','Semarang',-6.9667,110.4167),
  ('East Java','Surabaya',-7.2575,112.7521),
  ('Banten','Serang',-6.1200,106.1503),
  ('Yogyakarta','Yogyakarta',-7.7956,110.3695),
  ('North Sumatra','Medan',3.5952,98.6722),
  ('South Sumatra','Palembang',-2.9761,104.7754),
  ('West Sumatra','Padang',-0.9471,100.4172),
  ('Riau','Pekanbaru',0.5071,101.4478),
  ('Lampung','Bandar Lampung',-5.3971,105.2668),
  ('Bali','Denpasar',-8.6705,115.2126),
  ('South Sulawesi','Makassar',-5.1477,119.4327),
  ('North Sulawesi','Manado',1.4748,124.8421),
  ('East Kalimantan','Samarinda',-0.5022,117.1536),
  ('West Kalimantan','Pontianak',-0.0263,109.3425);
