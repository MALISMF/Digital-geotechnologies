import folium
import json
import pandas as pd
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union
import numpy as np

def load_geojson_data(filename):
    """Загружает данные из GeoJSON файла"""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_administrative_regions(data):
    """Извлекает административные округа из данных"""
    regions = []
    for feature in data['features']:
        if (feature['properties'].get('boundary') == 'administrative' and 
            feature['properties'].get('admin_level') == '9'):
            regions.append(feature)
    return regions

def extract_universities(data):
    """Извлекает университеты из данных"""
    universities = []
    for feature in data['features']:
        # Ищем объекты с amenity: university ИЛИ building: university
        if (feature['properties'].get('amenity') == 'university' or 
            feature['properties'].get('building') == 'university'):
            universities.append(feature)
    return universities

def get_geometry_center(geometry):
    """Получает центр геометрии"""
    if geometry['type'] == 'Point':
        return Point(geometry['coordinates'])
    elif geometry['type'] == 'Polygon':
        coords = geometry['coordinates'][0]
        return Point(np.mean([coord[0] for coord in coords]), 
                    np.mean([coord[1] for coord in coords]))
    elif geometry['type'] == 'MultiPolygon':
        # Для MultiPolygon берем центр первого полигона
        coords = geometry['coordinates'][0][0]
        return Point(np.mean([coord[0] for coord in coords]), 
                    np.mean([coord[1] for coord in coords]))
    return None

def point_in_polygon(point, polygon_coords):
    """Проверяет, находится ли точка внутри полигона"""
    point_obj = Point(point)
    polygon_obj = Polygon(polygon_coords)
    return polygon_obj.contains(point_obj)

def count_universities_in_regions(regions, universities):
    """Подсчитывает количество университетов в каждом регионе"""
    region_counts = {}
    
    for region in regions:
        region_name = region['properties']['name']
        region_geometry = region['geometry']
        count = 0
        region_universities = []
        
        # Получаем координаты полигона региона
        if region_geometry['type'] == 'Polygon':
            polygon_coords = region_geometry['coordinates'][0]
        elif region_geometry['type'] == 'MultiPolygon':
            # Для MultiPolygon объединяем все полигоны
            all_coords = []
            for poly in region_geometry['coordinates']:
                all_coords.extend(poly[0])
            polygon_coords = all_coords
        else:
            continue
            
        # Проверяем каждый университет
        for university in universities:
            uni_center = get_geometry_center(university['geometry'])
            if uni_center and point_in_polygon([uni_center.x, uni_center.y], polygon_coords):
                count += 1
                region_universities.append(university)
        
        region_counts[region_name] = {
            'count': count,
            'universities': region_universities,
            'region': region
        }
    
    return region_counts

def create_university_map(geojson_file):
    """Создает карту университетов с использованием Folium"""
    
    # Загружаем данные
    data = load_geojson_data(geojson_file)
    
    # Извлекаем административные регионы и университеты
    regions = extract_administrative_regions(data)
    universities = extract_universities(data)
    
    # Подсчитываем университеты по регионам
    region_counts = count_universities_in_regions(regions, universities)
    
    # Создаем базовую карту (центр Иркутска)
    m = folium.Map(
        location=[52.2871, 104.3056],  # Координаты Иркутска
        zoom_start=11,
        tiles='OpenStreetMap'
    )
    
    # Определяем цветовую схему на основе количества университетов (непрерывная шкала)
    counts = [info['count'] for info in region_counts.values()]
    min_count = min(counts) if counts else 0
    max_count = max(counts) if counts else 1
    
    def get_color(count, min_count, max_count):
        """Возвращает цвет на основе сине-голубой шкалы, гармонирующей с границами и значками университетов"""
        if max_count == min_count:
            return '#E6F3FF'  # Очень светло-голубой если все значения одинаковые
        
        # Нормализуем значение от 0 до 1
        normalized = (count - min_count) / (max_count - min_count)
        
        # Создаем градиент от светло-голубого к темно-синему
        # Светло-голубой: #E6F3FF (230, 243, 255)
        # Темно-синий: #120a8f (18, 10, 143)
        red = int(230 - 212 * normalized)  # 230 - 212 = 18
        green = int(243 - 233 * normalized)  # 243 - 233 = 10
        blue = int(255 - 112 * normalized)  # 255 - 112 = 143
        
        return f'#{red:02x}{green:02x}{blue:02x}'
    
    # Добавляем административные регионы
    for region_name, info in region_counts.items():
        region = info['region']
        count = info['count']
        color = get_color(count, min_count, max_count)
        
        # Создаем GeoJSON для региона
        region_geojson = {
            "type": "Feature",
            "properties": {
                "name": region_name,
                "university_count": count,
                "fillColor": color,
                "fillOpacity": 0.3,
                "color": color,
                "weight": 2
            },
            "geometry": region['geometry']
        }
        
        # Добавляем регион на карту
        folium.GeoJson(
            region_geojson,
            style_function=lambda x, color=color: {
                'fillColor': color,
                'color': color,
                'weight': 1,
                'fillOpacity': 0.6
            },
            popup=folium.Popup(
                f"<b>{region_name}</b><br>"
                f"Количество университетов: {count}",
                max_width=300
            )
        ).add_to(m)
        
        # Добавляем университеты в этом регионе
        for university in info['universities']:
            uni_name = university['properties'].get('name', 'Неизвестный университет')
            uni_geometry = university['geometry']
            uni_center = get_geometry_center(uni_geometry)
            
            # Добавляем границы университета, если они есть (Way и Relation)
            if uni_geometry['type'] in ['Polygon', 'MultiPolygon']:
                # Создаем GeoJSON для границ университета
                university_geojson = {
                    "type": "Feature",
                    "properties": {
                        "name": uni_name,
                        "type": "university_boundary"
                    },
                    "geometry": uni_geometry
                }
                
                # Добавляем границы университета
                folium.GeoJson(
                    university_geojson,
                    style_function=lambda x: {
                        'fillColor': '#120a8f',
                        'color': '#1d1d8f',
                        'weight': 2,
                        'fillOpacity': 0.4,
                        'dashArray': '5, 5'
                    },
                    popup=folium.Popup(
                        f"<b>Границы: {uni_name}</b>",
                        max_width=300
                    )
                ).add_to(m)
            
            # Добавляем маркер университета
            if uni_center:
                # Создаем HTML для иконки университета
                icon_html = """
                <div style="
                    background-color: #a6caf0;
                    width: 40px;
                    height: 40px;
                    border-radius: 30%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 40px;
                    border: 2px solid white;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                ">
                    🎓
                </div>
                """
                
                # Добавляем маркер
                folium.Marker(
                    location=[uni_center.y, uni_center.x],
                    popup=folium.Popup(
                        f"<b>{uni_name}</b><br>"
                        f"Регион: {region_name}",
                        max_width=300
                    ),
                    icon=folium.DivIcon(
                        html=icon_html,
                        icon_size=(30, 30),
                        icon_anchor=(15, 15)
                    )
                ).add_to(m)
    
    # Создаем цветовую шкалу для легенды
    def create_color_scale_legend(min_val, max_val):
        """Создает HTML для цветовой шкалы с четкими блоками"""
        if max_val == min_val:
            return f'<div style="width: 100%; height: 20px; background: #00ff00; border: 1px solid #000;"></div><p style="text-align: center; margin: 2px 0; font-size: 12px;">{min_val}</p>'
        
        # Определяем количество блоков и их цвета (соответствуют цветам на карте)
        num_blocks = 5
        # Сине-голубая палитра, гармонирующая с границами и значками университетов
        colors = ['#E6F3FF', '#B3D9FF', '#80BFFF', '#4A90E2', '#120a8f']
        
        # Создаем четкие блоки
        block_width = 100 / num_blocks
        blocks_html = '<div style="display: flex; width: 100%; height: 20px; border: 1px solid #000;">'
        
        for i in range(num_blocks):
            blocks_html += f'<div style="width: {block_width}%; height: 100%; background: {colors[i]}; border-right: 1px solid #000;"></div>'
        
        blocks_html += '</div>'
        
        # Добавляем числовые метки (целые числа)
        num_ticks = 6  # Количество делений на шкале
        tick_values = []
        for i in range(num_ticks):
            value = min_val + (max_val - min_val) * i / (num_ticks - 1)
            tick_values.append(int(round(value)))
        
        # Создаем HTML для меток
        ticks_html = '<div style="display: flex; justify-content: space-between; margin-top: 2px;">'
        for value in tick_values:
            ticks_html += f'<span style="font-size: 10px;">{value}</span>'
        ticks_html += '</div>'
        
        return blocks_html + ticks_html
    
    # Подсчитываем общее количество университетов
    total_universities = sum([info['count'] for info in region_counts.values()])
    
    # Добавляем легенду с цветовой шкалой
    legend_html = f'''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 350px; height: 140px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px; border-radius: 5px;">
    <div style="display: flex; align-items: flex-start; gap: 15px;">
        <div style="flex: 1;">
            <p style="margin: 0 0 10px 0; text-align: center;"><b>Количество корпусов</b></p>
            {create_color_scale_legend(min_count, max_count)}
        </div>
        <div style="flex: 0 0 auto; margin-top: 5px;">
            <p style="font-size: 11px; margin: 2px 0; text-align: left;"><b>Обозначения:</b></p>
            <p style="font-size: 10px; margin: 1px 0; text-align: left;">🎓 Маркер университета</p>
            <p style="font-size: 10px; margin: 1px 0; text-align: left;">🔵 Границы университета</p>
        </div>
    </div>
    <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #ccc; text-align: center;">
        <p style="font-size: 12px; margin: 2px 0;"><b>Общее количество корпусов: {total_universities}</b></p>
    </div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Добавляем заголовок
    title_html = '''
    <h3 style="font-size:20px; margin-top:15px;position:absolute;z-index: 1000;text-align: center;width: 100%;">
    <b style = "padding:10px; border-radius:5px;background:white;border:2px solid grey;">Количество университетов Иркутска по административным регионам</b>
    </h3>
    '''
    m.get_root().html.add_child(folium.Element(title_html))
    
    return m, region_counts

def main():
    """Основная функция"""
    # Создаем карту
    map_obj, region_counts = create_university_map('ARuni.geojson')
    
    # Сохраняем карту
    output_file = 'university_map.html'
    map_obj.save(output_file)

if __name__ == "__main__":
    main()
