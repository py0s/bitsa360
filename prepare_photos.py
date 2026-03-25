#!/usr/bin/env python3
"""
Подготовка 360-фото с Insta360 для карты Битцевского леса.

Использование:
    python3 prepare_photos.py /path/to/insta360/photos

Скрипт:
1. Читает GPS-координаты из EXIF каждого фото
2. Копирует фото в папку 360photos/ с нормальными именами
3. Привязывает каждое фото к ближайшей входной группе
4. Обновляет entry_points.json
"""

import sys
import json
import shutil
import math
from pathlib import Path

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    print("Нужна библиотека Pillow:")
    print("  pip3 install Pillow")
    sys.exit(1)


def get_exif_data(image_path):
    """Извлекает EXIF-данные из изображения."""
    try:
        img = Image.open(image_path)
        exif = img._getexif()
        if not exif:
            return None
        return {TAGS.get(k, k): v for k, v in exif.items()}
    except Exception as e:
        print(f"  Ошибка чтения EXIF: {e}")
        return None


def get_gps_coords(exif_data):
    """Извлекает GPS-координаты из EXIF."""
    if not exif_data or 'GPSInfo' not in exif_data:
        return None

    gps_info = exif_data['GPSInfo']
    gps = {GPSTAGS.get(k, k): v for k, v in gps_info.items()}

    if 'GPSLatitude' not in gps or 'GPSLongitude' not in gps:
        return None

    def to_degrees(value):
        d, m, s = value
        return float(d) + float(m) / 60 + float(s) / 3600

    lat = to_degrees(gps['GPSLatitude'])
    lng = to_degrees(gps['GPSLongitude'])

    if gps.get('GPSLatitudeRef', 'N') == 'S':
        lat = -lat
    if gps.get('GPSLongitudeRef', 'E') == 'W':
        lng = -lng

    return (lat, lng)


def get_datetime(exif_data):
    """Извлекает дату съёмки из EXIF."""
    if not exif_data:
        return None
    return exif_data.get('DateTimeOriginal') or exif_data.get('DateTime')


def haversine(lat1, lng1, lat2, lng2):
    """Расстояние между двумя GPS-точками в метрах."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest_entry(lat, lng, entry_points):
    """Находит ближайшую входную группу."""
    best = None
    best_dist = float('inf')
    for ep in entry_points:
        dist = haversine(lat, lng, ep['lat'], ep['lng'])
        if dist < best_dist:
            best_dist = dist
            best = ep
    return best, best_dist


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 prepare_photos.py /путь/к/папке/с/фото")
        print()
        print("Поддерживаемые форматы: .jpg, .jpeg, .insp, .png")
        sys.exit(1)

    photos_dir = Path(sys.argv[1])
    if not photos_dir.is_dir():
        print(f"Папка не найдена: {photos_dir}")
        sys.exit(1)

    script_dir = Path(__file__).parent
    output_dir = script_dir / '360photos'
    output_dir.mkdir(exist_ok=True)

    # Загружаем entry_points.json
    ep_file = script_dir / 'entry_points.json'
    if not ep_file.exists():
        print("entry_points.json не найден!")
        sys.exit(1)

    with open(ep_file, 'r', encoding='utf-8') as f:
        entry_points = json.load(f)

    # Ищем фото
    extensions = {'.jpg', '.jpeg', '.insp', '.png', '.JPG', '.JPEG', '.INSP'}
    photos = [p for p in photos_dir.iterdir() if p.suffix in extensions]

    if not photos:
        print(f"Не найдено фото в {photos_dir}")
        print(f"Поддерживаемые форматы: {', '.join(sorted(extensions))}")
        sys.exit(1)

    print(f"Найдено {len(photos)} фото в {photos_dir}")
    print(f"{'='*60}")

    assigned = {}  # entry_id -> list of (photo_path, distance)
    no_gps = []
    processed = 0

    for photo in sorted(photos):
        print(f"\n📷 {photo.name}")

        # Для .insp файлов — это JPEG внутри, Pillow может их читать
        exif = get_exif_data(photo)
        coords = get_gps_coords(exif)
        dt = get_datetime(exif)

        if coords:
            lat, lng = coords
            print(f"  GPS: {lat:.6f}, {lng:.6f}")
            if dt:
                print(f"  Дата: {dt}")

            nearest, dist = find_nearest_entry(lat, lng, entry_points)
            print(f"  Ближайшая: {nearest['name']} ({dist:.0f} м)")

            eid = nearest['id']
            if eid not in assigned:
                assigned[eid] = []
            assigned[eid].append((photo, dist, coords))
            processed += 1
        else:
            print("  ⚠️  GPS не найден")
            no_gps.append(photo)

    print(f"\n{'='*60}")
    print(f"РЕЗУЛЬТАТ:")
    print(f"  Обработано с GPS: {processed}")
    print(f"  Без GPS: {len(no_gps)}")

    # Копируем фото и обновляем entry_points
    for eid, photos_list in assigned.items():
        # Берём ближайшее фото для каждой входной группы
        photos_list.sort(key=lambda x: x[1])
        best_photo, best_dist, best_coords = photos_list[0]

        # Копируем
        ext = best_photo.suffix.lower()
        if ext == '.insp':
            ext = '.jpg'
        out_name = f"vg{eid}{ext}"
        out_path = output_dir / out_name

        shutil.copy2(best_photo, out_path)
        print(f"  ВГ{eid}: {best_photo.name} → {out_name} ({best_dist:.0f} м)")

        # Обновляем entry_points
        for ep in entry_points:
            if ep['id'] == eid:
                ep['photo360'] = f"360photos/{out_name}"
                # Обновляем координаты на точные из GPS
                ep['lat'] = round(best_coords[0], 6)
                ep['lng'] = round(best_coords[1], 6)
                break

        # Если есть дополнительные фото — тоже копируем
        for i, (photo, dist, coords) in enumerate(photos_list[1:], 1):
            ext = photo.suffix.lower()
            if ext == '.insp':
                ext = '.jpg'
            extra_name = f"vg{eid}_extra{i}{ext}"
            shutil.copy2(photo, output_dir / extra_name)

    # Сохраняем обновлённый entry_points.json
    with open(ep_file, 'w', encoding='utf-8') as f:
        json.dump(entry_points, f, ensure_ascii=False, indent=2)

    print(f"\n✅ entry_points.json обновлён")

    # Отчёт о покрытии
    covered = sum(1 for ep in entry_points if ep.get('photo360'))
    total = len(entry_points)
    print(f"\n📊 Покрытие: {covered}/{total} входных групп")

    uncovered = [ep for ep in entry_points if not ep.get('photo360')]
    if uncovered:
        print(f"\n❌ Без фото:")
        for ep in uncovered:
            print(f"  • {ep['name']} — {ep['description']}")

    if no_gps:
        print(f"\n⚠️  Фото без GPS (не привязаны):")
        for p in no_gps:
            print(f"  • {p.name}")


if __name__ == '__main__':
    main()
