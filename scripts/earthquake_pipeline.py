import sys, os
import re
import json
import hashlib
import datetime
from django.db import transaction, IntegrityError
from django.contrib.gis.geos import Point
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from itertools import groupby
from operator import itemgetter

sys.path.append("/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend_core.settings")

import django
django.setup()

from django.conf import settings
from api.models import Earthquake, DuplicateLink, IntensityCurve, Plate, Country, SyncState

URL_IGN = "https://www.ign.es/web/resources/sismologia/tproximos/terremotos.js"
URL_USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query"
URL_EMSC = "https://www.seismicportal.eu/fdsnws/event/1/query"

state, _ = SyncState.objects.get_or_create(key="initial_sync_done")
initial_sync = not state.value

today = datetime.datetime.now(datetime.UTC)
tomorrow = today + datetime.timedelta(days=1)

state, _ = SyncState.objects.get_or_create(key="initial_sync_done")
initial_sync = not state.value

today = datetime.datetime.now(datetime.UTC)
tomorrow = today + datetime.timedelta(days=1)

if initial_sync:
    print("[*] Running initial sync (first execution)")
    last_event = Earthquake.objects.order_by("-retrieved_time").only("retrieved_time").first()
    if last_event is None:
        start_time = today - datetime.timedelta(days=30)
        print("[*] No events found - fetching last 30 days.")
    else:
        start_time = last_event.retrieved_time - datetime.timedelta(days=1)
        print(f"[*] Found existing events - fetching from {start_time.isoformat()}")

    state.value = True
    state.last_sync_start = start_time
    state.last_sync_end = tomorrow
    state.last_run_at = today
    state.save()

else:
    start_time = today - datetime.timedelta(days=1)

    state.last_sync_start = start_time
    state.last_sync_end = tomorrow
    state.last_run_at = today
    state.save()

params_USGS = {
    "format": "geojson",
    "starttime": start_time.isoformat(),
    "endtime": tomorrow.isoformat(),
}

params_EMSC = {
    "format": "json",
    "starttime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
    "endtime": tomorrow.strftime("%Y-%m-%dT%H:%M:%S"),
}

# ==========================================================

def generate_global_id(source, source_id):
    key = f"{source.strip().upper()}::{source_id.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

def safe_float(value):
    try:
        if value in [None, "", "NaN", "nan"]:
            return None
        return float(value)
    except Exception:
        return None

def safe_bool(value):
    if value in [None, "", "NaN", "nan"]:
        return None
    s = str(value).strip().lower()
    if s in ["true", "1", "yes"]:
        return True
    if s in ["false", "0", "no"]:
        return False
    return None

def standardize_date(value):
    if value is None:
        return None

    if isinstance(value, datetime.datetime):
        return value.astimezone(datetime.UTC) if value.tzinfo else value.replace(tzinfo=datetime.UTC)

    if isinstance(value, (int, float)):
        return datetime.datetime.fromtimestamp(value / 1000, tz=datetime.UTC)

    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                value = value.replace("Z", "+00:00")
            return datetime.datetime.fromisoformat(value).astimezone(datetime.UTC)
        except Exception:
            return None

    return None

# ==========================================================

def get_IGN_events():
    try:
        response = requests.get(URL_IGN, timeout=20)
        response.raise_for_status()

        match = re.search(r"var\s+dias3\s*=\s*({.*?});", response.text, re.DOTALL)
        if not match:
            print("[!] IGN JSON block not found")
            return []

        data = json.loads(match.group(1))
    except Exception as e:
        print(f"[!] Error fetching IGN data: {e}")
        return []

    retrieved_time_utc = standardize_date(datetime.datetime.now(datetime.UTC))
    events = []

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [None, None, None])

        source = "IGN"

        evid = (props.get("evid") or "").strip() or f"{coords[0]}_{coords[1]}"
        source_id = f"{source}_{evid}"

        events.append({
            "source": source,
            "source_id": source_id,
            "global_id": generate_global_id(source, source_id),
            "magnitude": props.get("mag"),
            "mag_type": props.get("magtype"),
            "place_name": props.get("loc"),
            "latitude": coords[1],
            "longitude": coords[0],
            "depth_km": props.get("depth"),
            "origin_time_utc": props.get("fecha"),
            "updated_time_utc": None,
            "retrieved_time_utc": retrieved_time_utc,
            "raw_data": feature
        })
    return events

def get_USGS_events():
    try:
        response = requests.get(URL_USGS, params=params_USGS, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[!] Error fetching USGS data: {e}")
        return []

    retrieved_time_utc = standardize_date(datetime.datetime.now(datetime.UTC))
    events = []

    for feature in data.get("features", []):
        props = feature.get("properties", {}) or {}
        geom = feature.get("geometry", {}) or {}
        coords = geom.get("coordinates", [None, None, None])

        if not props.get("type") or props.get("type").lower() != "earthquake":
            continue

        source = "USGS"
        source_id = f"{source}_{feature.get('id')}"

        events.append({
            "source": source,
            "source_id": source_id,
            "global_id": generate_global_id(source, source_id),
            "magnitude": props.get("mag"),
            "mag_type": props.get("magType"),
            "place_name": props.get("place"),
            "latitude": coords[1],
            "longitude": coords[0],
            "depth_km": coords[2],
            "origin_time_utc": props.get("time"),
            "updated_time_utc": props.get("updated"),
            "retrieved_time_utc": retrieved_time_utc,
            "tsunami": props.get("tsunami"),
            "has_shakemap": "shakemap" in (props.get("types") or ""),
            "raw_data": feature
        })
    return events

def get_EMSC_events():
    try:
        response = requests.get(URL_EMSC, params=params_EMSC, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[!] Error fetching EMSC data: {e}")
        return []

    retrieved_time_utc = standardize_date(datetime.datetime.now(datetime.UTC))
    events = []

    for feature in data.get("features", []):
        props = feature.get("properties", {}) or {}
        geom = feature.get("geometry", {}) or {}
        coords = geom.get("coordinates", [None, None, None])
        
        if not props.get("evtype") or props.get("evtype").lower() not in ["ke", "fe"]:
            continue

        source = "EMSC"
        source_id = f"{source}_{(props.get('unid') or '').strip()}"

        events.append({
            "source": source,
            "source_id": source_id,
            "global_id": generate_global_id(source, source_id),
            "magnitude": props.get("mag"),
            "mag_type": props.get("magtype"),
            "place_name": props.get("flynn_region"),
            "latitude": coords[1],
            "longitude": coords[0],
            "depth_km": coords[2],
            "origin_time_utc": props.get("time"),
            "updated_time_utc": props.get("lastupdate"),
            "retrieved_time_utc": retrieved_time_utc,
            "raw_data": feature
        })
    return events

# ==========================================================

def get_tectonic_plate(event_coords):
    point = Point(event_coords[0], event_coords[1], srid=4326)
    match = Plate.objects.filter(geom__intersects=point).first()
    if not match:
        return None
    return match.platename or match.code or None

def get_origin_country(event_coords):
    point = Point(event_coords[0], event_coords[1], srid=4326)
    match = Country.objects.filter(geom__intersects=point).first()
    if not match:
        return None
    return match.admin or match.sovereignt or None

def get_affected_countries(contours):
    points = []
    for _, coords in contours:
        for polygon in coords:
            for lon, lat in polygon:
                points.append(Point(lon, lat, srid=4326))

    countries = set()
    for pt in points:
        match = Country.objects.filter(geom__intersects=pt).first()
        if match:
            countries.add(match.admin or match.sovereignt)

    return list(filter(None, countries))

def get_intensity_contours(source_id):
    event_id = source_id.split("_", 1)[1] if source_id.startswith("USGS_") else source_id
    detail_url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?eventid={event_id}&format=geojson"
    try:
        detail_data = requests.get(detail_url, timeout=20).json()
        curve_match = re.findall(r"https://[^\s\"']+cont_mmi\.json", json.dumps(detail_data))
        if not curve_match:
            return []
        curve_url = curve_match[0]
        curve_data = requests.get(curve_url, timeout=20).json()
        return [
            (feature["properties"]["value"], feature["geometry"]["coordinates"])
            for feature in curve_data.get("features", [])
        ]
    except Exception as e:
        print(f"[!] Error fetching MMI contours for {source_id}: {e}")
        return []

# ==========================================================

def enrich_event_metadata(event):
    lon, lat = event["longitude"], event["latitude"]

    try:
        event["tectonic_plate"] = get_tectonic_plate((lon, lat))
    except Exception as e:
        print(f"[!] Error assigning tectonic plate: {e}")
        event["tectonic_plate"] = None

    try:
        event["origin_country"] = get_origin_country((lon, lat))
    except Exception as e:
        print(f"[!] Error assigning origin country: {e}")
        event["origin_country"] = None

    event["affected_countries"] = []
    if event.get("has_shakemap") and event.get("source_id"):
        try:
            contours = get_intensity_contours(event["source_id"])
            if contours:
                affected = get_affected_countries(contours)
                event["affected_countries"] = affected if affected else []
                event["intensity_contours"] = contours
        except Exception as e:
            print(f"[!] Error retrieving shakemap for {event.get('source_id')}: {e}")

    return event

def create_event(event_info, source):
    global_id = event_info.get("global_id")
    existing = Earthquake.objects.filter(global_id=global_id).first()

    updated_dt = standardize_date(event_info.get("updated_time_utc"))
    if existing:
        if updated_dt and (existing.updated_time is None or updated_dt > existing.updated_time):
            event_info["latitude"] = safe_float(event_info.get("latitude"))
            event_info["longitude"] = safe_float(event_info.get("longitude"))
            depth_val = safe_float(event_info.get("depth_km"))
            event_info["depth_km"] = abs(depth_val) if depth_val is not None else None
            event_info["magnitude"] = safe_float(event_info.get("magnitude"))
            event_info["tsunami"] = safe_bool(event_info.get("tsunami"))
            event_info["has_shakemap"] = safe_bool(event_info.get("has_shakemap"))
            event_info["origin_time_utc"] = standardize_date(event_info.get("origin_time_utc"))
            event_info["retrieved_time_utc"] = standardize_date(event_info.get("retrieved_time_utc"))
            event_info["place_name"] = event_info.get("place_name") or None
            event_info["mag_type"] = event_info.get("mag_type") or None

            event_info = enrich_event_metadata(event_info)

            for field, value in {
                "origin_time": event_info.get("origin_time_utc"),
                "latitude": event_info.get("latitude"),
                "longitude": event_info.get("longitude"),
                "place_name": event_info.get("place_name"),
                "depth_km": event_info.get("depth_km"),
                "magnitude": event_info.get("magnitude"),
                "mag_type": event_info.get("mag_type"),
                "tectonic_plate": event_info.get("tectonic_plate"),
                "origin_country": event_info.get("origin_country"),
                "affected_countries": event_info.get("affected_countries", []),
                "updated_time": updated_dt,
                "retrieved_time": event_info.get("retrieved_time_utc"),
                "tsunami": event_info.get("tsunami"),
                "has_curves": event_info.get("has_shakemap"),
                "raw_data": event_info.get("raw_data") or {},
            }.items():
                setattr(existing, field, value)

            existing.save()
            return existing, "updated"
        return existing, "unchanged"

    event_info["latitude"] = safe_float(event_info.get("latitude"))
    event_info["longitude"] = safe_float(event_info.get("longitude"))
    event_info["depth_km"] = safe_float(event_info.get("depth_km"))
    event_info["magnitude"] = safe_float(event_info.get("magnitude"))
    event_info["tsunami"] = safe_bool(event_info.get("tsunami"))
    event_info["has_shakemap"] = safe_bool(event_info.get("has_shakemap"))
    event_info["origin_time_utc"] = standardize_date(event_info.get("origin_time_utc"))
    event_info["updated_time_utc"] = updated_dt
    event_info["retrieved_time_utc"] = standardize_date(event_info.get("retrieved_time_utc"))
    event_info["place_name"] = event_info.get("place_name") or None
    event_info["mag_type"] = event_info.get("mag_type") or None

    event_info = enrich_event_metadata(event_info)

    try:
        with transaction.atomic():
            event = Earthquake.objects.create(
                global_id=global_id,
                source=source,
                source_id=event_info.get("source_id"),
                origin_time=event_info.get("origin_time_utc"),
                latitude=event_info.get("latitude"),
                longitude=event_info.get("longitude"),
                place_name=event_info.get("place_name"),
                depth_km=event_info.get("depth_km"),
                magnitude=event_info.get("magnitude"),
                mag_type=event_info.get("mag_type"),
                tectonic_plate=event_info.get("tectonic_plate"),
                origin_country=event_info.get("origin_country"),
                affected_countries=event_info.get("affected_countries", []),
                updated_time=updated_dt,
                retrieved_time=event_info.get("retrieved_time_utc"),
                tsunami=event_info.get("tsunami"),
                has_curves=event_info.get("has_shakemap"),
                raw_data=event_info.get("raw_data") or {},
            )
    except IntegrityError:
        print(f"[!] Skipped duplicate event {event_info.get('source_id')}.")
        return Earthquake.objects.filter(global_id=global_id).first(), "unchanged"

    if event_info.get("has_shakemap") and "intensity_contours" in event_info:
        for intensity, coordinates in event_info["intensity_contours"]:
            IntensityCurve.objects.create(
                earthquake=event,
                intensity=safe_float(intensity),
                coordinates=coordinates
            )
        event.has_curves = True
        event.save(update_fields=["has_curves"])

    return event, "new"

def process_events(event_data):
    counts = {"new": 0, "updated": 0, "unchanged": 0}

    def handle_event(event_info):
        try:
            _, status = create_event(event_info, event_info.get("source"))
            return status
        except Exception as e:
            print(f"[!] Error processing {event_info.get('source_id', 'unknown')}: {e}")
            return "error"

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(handle_event, event_data))

    for status in results:
        if status in counts:
            counts[status] += 1

    return counts["new"], counts["updated"], counts["unchanged"]

# ==========================================================

def mark_duplicates(dt_threshold=8, dd_threshold=8, dm_threshold=0.7, source_priority={"USGS": 0, "IGN": 1, "EMSC": 2}):
    events = list(
        Earthquake.objects.filter(duplicate_of__isnull=True)
        .exclude(location__isnull=True)
        .order_by("origin_time")
    )

    total_links = 0
    total_checked = 0
    n = len(events)

    def process_event(i):
        event_a = events[i]
        local_links = 0
        local_checked = 0

        for j in range(i + 1, n):
            event_b = events[j]
            dt = (event_b.origin_time - event_a.origin_time).total_seconds()

            if dt > dt_threshold:
                break

            if event_a.source == event_b.source:
                continue

            local_checked += 1
            if event_a.magnitude is None or event_b.magnitude is None:
                continue

            dm = abs(event_a.magnitude - event_b.magnitude)
            if dm > dm_threshold:
                continue

            try:
                dd = event_a.location.distance(event_b.location) / 1000
            except Exception:
                continue

            if dd <= dd_threshold:
                pa = source_priority.get((event_a.source or "").strip(), 99)
                pb = source_priority.get((event_b.source or "").strip(), 99)
                canonical = event_a if pa < pb else event_b
                duplicate = event_b if canonical == event_a else event_a

                if DuplicateLink.objects.filter(canonical=canonical, duplicate=duplicate).exists():
                    continue

                with transaction.atomic():
                    DuplicateLink.objects.create(
                        canonical=canonical,
                        duplicate=duplicate,
                        dt=dt,
                        dd=dd,
                        dm=dm,
                    )
                    duplicate.duplicate_of = canonical
                    duplicate.save(update_fields=["duplicate_of"])

                local_links += 1

        return local_links, local_checked

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(process_event, range(n)))

    for links, checked in results:
        total_links += links
        total_checked += checked

    return total_links

def fetch_all_events():
    sources = {
        "USGS": get_USGS_events,
        "IGN": get_IGN_events,
        "EMSC": get_EMSC_events,
    }

    events_by_source = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_source = {executor.submit(func): name for name, func in sources.items()}

        for future in as_completed(future_to_source):
            name = future_to_source[future]
            try:
                result = future.result()
                events_by_source[name] = result
            except Exception as e:
                print(f"[!] Failed to retrieve {name} events: {e}")
                events_by_source[name] = []

    all_events = sum(events_by_source.values(), [])

    return all_events

# ==========================================================

if __name__ == "__main__":
    start = datetime.datetime.now(datetime.UTC)
    print(f"[*] Scheduled task triggered at {start}")

    all_events = fetch_all_events()

    all_events.sort(key=lambda e: (e.get("global_id"), e.get("updated_time_utc")),reverse=True)
    unique_events = []
    for gid, group in groupby(all_events, key=itemgetter("global_id")):
        first = next(group)
        unique_events.append(first)

    all_events = unique_events

    new_events, updated_events, unchanged = process_events(all_events)
    total_links = mark_duplicates()

    end = datetime.datetime.now(datetime.UTC)
    duration = (end - start).total_seconds()

    print(f"[✓] Cycle completed at {end.isoformat()} ({duration:.1f}s total) | New: {new_events} | Updated: {updated_events} | Unchanged: {unchanged} | Duplicated: {total_links}")