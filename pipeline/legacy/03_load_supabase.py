# -*- coding: utf-8 -*-
"""03_load_supabase.py — parcels 원장 Supabase(PostGIS) 적재
=================================================================
사전조건: pipeline/.env 에 SUPABASE_DB_URL=postgresql://... (Session pooler 권장)
입력: pipeline_out/parcels_final/{sgg}.parquet
동작: parcels 테이블 생성(승인 스키마) → 시군별 COPY 적재 → 건수 검증

사용: python 03_load_supabase.py [--recreate] [sgg콤마목록|all]
"""
import os, sys, io, glob, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd

BASE = r"C:\Users\user\새 폴더"
FINAL_DIR = os.path.join(BASE, "pipeline_out", "parcels_final")
ENV_PATH = os.path.join(BASE, "pipeline", ".env")

def load_env():
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        sys.exit("[중단] SUPABASE_DB_URL 없음 — pipeline/.env에 설정 필요")
    return url

DDL = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS parcels (
  pnu                 char(19) PRIMARY KEY,
  sgg_code            char(5)  NOT NULL,
  emd_code            char(8)  NOT NULL,
  dong_code           char(10) NOT NULL,
  geom                geometry(Point, 4326) NOT NULL,
  area_m2             numeric(12,1) NOT NULL,
  jimok               char(2)  NOT NULL,
  use_zone            text,
  agpromo_class       text NOT NULL,
  owner_class         text NOT NULL,
  is_facility         boolean NOT NULL DEFAULT false,
  slope_mean          real,
  excl_heritage       boolean NOT NULL DEFAULT false,
  excl_wildlife       boolean NOT NULL DEFAULT false,
  excl_natpark        boolean NOT NULL DEFAULT false,
  excl_baekdu         boolean NOT NULL DEFAULT false,
  excl_greenbuf       boolean NOT NULL DEFAULT false,
  excl_village        boolean NOT NULL DEFAULT false,
  excl_slope15        boolean NOT NULL DEFAULT false,
  excl_water          boolean NOT NULL DEFAULT false,
  excl_mil_control    boolean NOT NULL DEFAULT false,
  mil_limited         boolean NOT NULL DEFAULT false,
  excl_nature_zone    boolean NOT NULL DEFAULT false,
  excl_tech           boolean NOT NULL DEFAULT false,
  restrict_overlap_ratio real,
  s0_eligible         boolean NOT NULL,
  s2_eligible         boolean NOT NULL,
  indiv_ratio         real,
  dist_complex_km     real,
  updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_parcels_geom ON parcels USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_parcels_sgg_s3 ON parcels (sgg_code, s2_eligible);
CREATE INDEX IF NOT EXISTS idx_parcels_emd ON parcels (emd_code);
CREATE INDEX IF NOT EXISTS idx_parcels_dong ON parcels (dong_code);
CREATE INDEX IF NOT EXISTS idx_parcels_indiv ON parcels (indiv_ratio);
"""

BOOL_COLS = ["is_facility", "excl_heritage", "excl_wildlife", "excl_natpark",
             "excl_baekdu", "excl_greenbuf", "excl_village", "excl_slope15",
             "excl_water", "excl_mil_control", "mil_limited",
             "excl_nature_zone", "excl_tech", "s0_eligible", "s2_eligible"]
COPY_COLS = ["pnu", "sgg_code", "emd_code", "dong_code", "lon", "lat",
             "area_m2", "jimok", "use_zone", "agpromo_class", "owner_class",
             "slope_mean", "restrict_overlap_ratio", "indiv_ratio",
             "dist_complex_km"] + BOOL_COLS


def main():
    import psycopg2
    url = load_env()
    args = sys.argv[1:]
    recreate = "--recreate" in args
    args = [a for a in args if not a.startswith("--")]
    target = args[0] if args else "all"

    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    if recreate:
        cur.execute("DROP TABLE IF EXISTS parcels CASCADE")
        print("기존 parcels 테이블 삭제")
    cur.execute(DDL)
    print("스키마 확인/생성 완료")

    files = sorted(glob.glob(os.path.join(FINAL_DIR, "*.parquet")))
    if target != "all":
        want = set(target.split(","))
        files = [f for f in files if os.path.basename(f).split(".")[0] in want]

    total = 0
    for f in files:
        sgg = os.path.basename(f).split(".")[0]
        t0 = time.time()
        df = pd.read_parquet(f)
        df = df.rename(columns={"sgg": "sgg_code"})
        for c in BOOL_COLS:
            df[c] = df[c].astype(bool)
        stage = df[COPY_COLS].copy()

        cur.execute("CREATE TEMP TABLE _stage (LIKE parcels INCLUDING DEFAULTS "
                    "EXCLUDING CONSTRAINTS) ")
        cur.execute("ALTER TABLE _stage DROP COLUMN geom, DROP COLUMN updated_at")
        cur.execute("ALTER TABLE _stage ADD COLUMN lon double precision, "
                    "ADD COLUMN lat double precision")
        buf = io.StringIO()
        stage.to_csv(buf, index=False, header=False, na_rep="\\N")
        buf.seek(0)
        cur.copy_expert(
            f"COPY _stage ({', '.join(COPY_COLS)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')",
            buf)
        cur.execute(f"""
            INSERT INTO parcels ({', '.join(c for c in COPY_COLS if c not in ('lon','lat'))}, geom)
            SELECT {', '.join(c for c in COPY_COLS if c not in ('lon','lat'))},
                   ST_SetSRID(ST_MakePoint(lon, lat), 4326)
            FROM _stage
            ON CONFLICT (pnu) DO NOTHING""")
        cur.execute("DROP TABLE _stage")
        cur.execute("SELECT COUNT(*) FROM parcels WHERE sgg_code=%s", (sgg,))
        n_db = cur.fetchone()[0]
        ok = "OK" if n_db == len(df) else "!! 건수불일치"
        print(f"  {sgg}: 로컬 {len(df):,} / DB {n_db:,} [{ok}] ({time.time()-t0:.0f}s)")
        total += len(df)

    cur.execute("SELECT COUNT(*) FROM parcels")
    print(f"\nDB 총 건수: {cur.fetchone()[0]:,} (로컬 적재분 {total:,})")
    conn.close()


if __name__ == "__main__":
    main()
