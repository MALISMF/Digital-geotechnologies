import geopandas as gpd
from shapely.geometry import Point
import pandas as pd
import numpy as np

# Загрузка данных
parks = gpd.read_file("irkutsk_parks_4326.geojson")
roads = gpd.read_file("roads_32648.geojson")
settlements = gpd.read_file("settlements_irk_obl_4326.geojson")

# Перепроецирование слоев из EPSG:4326 в EPSG:32648
roads = roads.set_crs('EPSG:32648')
parks = parks.to_crs('EPSG:32648')
settlements = settlements.to_crs('EPSG:32648')

# Поиск границ Иркутска
irkutsk_variants = ['Иркутск', 'Irkutsk', 'иркутск', 'IRKUTSK']
irkutsk_boundary = None

for variant in irkutsk_variants:
    if 'name' in settlements.columns:
        mask = settlements['name'].str.contains(variant, case=False, na=False)
        if mask.any():
            irkutsk_boundary = settlements[mask]
            break

if irkutsk_boundary is None or len(irkutsk_boundary) == 0:
    irkutsk_boundary = settlements.iloc[[0]]

# Обрезка данных по границам Иркутска
parks_clipped = gpd.clip(parks, irkutsk_boundary)
roads_clipped = gpd.clip(roads, irkutsk_boundary)

# Анализ структуры данных дорог
road_type_column = None
possible_columns = ['type', 'road_type', 'highway', 'class', 'category', 'fclass']
for col in possible_columns:
    if col in roads_clipped.columns:
        road_type_column = col
        break

if not road_type_column:
    roads_clipped['road_type'] = 'road'
    road_type_column = 'road_type'

# Рассчет количества разных дорог для парков в радиусе 100м
def count_unique_roads_in_radius(park, roads, radius=100):
    buffer = park.geometry.buffer(radius)
    intersecting_roads = roads[roads.geometry.intersects(buffer)]
    if len(intersecting_roads) > 0:
        unique_types = intersecting_roads[road_type_column].nunique()
        return unique_types
    else:
        return 0

parks_clipped['unique_roads_100m'] = parks_clipped.apply(
    lambda row: count_unique_roads_in_radius(row, roads_clipped, 100), axis=1
)

# Рассчет ближайшей дистанции до дороги и ID ближайшей дороги
def min_distance_to_road(park, roads):
    distances = roads.geometry.distance(park.geometry)
    min_dist = distances.min()
    nearest_road_idx = distances.idxmin()
    if 'id' in roads.columns:
        nearest_road_id = roads.loc[nearest_road_idx, 'id']
    else:
        nearest_road_id = nearest_road_idx
    return min_dist, nearest_road_id

# Применяем функцию и разделяем результаты
distance_results = parks_clipped.apply(
    lambda row: min_distance_to_road(row, roads_clipped), axis=1
)

parks_clipped['min_distance_to_road'] = [result[0] for result in distance_results]
parks_clipped['nearest_road_id'] = [result[1] for result in distance_results]

parks_clipped.to_file("parks_analysis_results.geojson", driver='GeoJSON')


print("Обрезка данных по границам г. Иркутска:")
print(f"   - Парков в границах города: {len(parks_clipped)}")
print(f"   - Дорог в границах города: {len(roads_clipped)}")
print()
print("Количество разных дорог для парков в радиусе 100м:")
print(f"   - Среднее количество: {parks_clipped['unique_roads_100m'].mean():.2f}")
print(f"   - Максимальное количество: {parks_clipped['unique_roads_100m'].max()}")
print(f"   - Минимальное количество: {parks_clipped['unique_roads_100m'].min()}")
print()
print("Ближайшая дистанция до дороги:")
print(f"   - Среднее расстояние: {parks_clipped['min_distance_to_road'].mean():.2f} м")
print(f"   - Максимальное расстояние: {parks_clipped['min_distance_to_road'].max():.2f} м")
print(f"   - Минимальное расстояние: {parks_clipped['min_distance_to_road'].min():.2f} м")
