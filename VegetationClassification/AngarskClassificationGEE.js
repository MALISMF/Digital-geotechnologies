// --- 1. ОПРЕДЕЛЕНИЕ РЕГИОНА И ДАННЫХ ---

// Геометрия для Ангарска
var geometry = ee.Geometry.Polygon([[
  [103.715, 52.595], // Северо-западная точка
  [103.715, 52.445], // Юго-западная точка
  [104.015, 52.445], // Юго-восточная точка
  [104.015, 52.595]  // Северо-восточная точка
]]); 
Map.centerObject(geometry, 11);

var year = 2019;
var startDate = ee.Date.fromYMD(year, 1, 1);
var endDate = startDate.advance(1, 'year');

// Загрузка Sentinel-2
var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED');

var filtered = s2
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
  .filter(ee.Filter.date(startDate, endDate))
  .filter(ee.Filter.bounds(geometry));

// Загрузка Cloud Score+ для маскирования облаков
var csPlus = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED');
var csPlusBands = csPlus.first().bandNames();

var filteredS2WithCs = filtered.linkCollection(csPlus, csPlusBands);

function maskLowQA(image) {
  var qaBand = 'cs';
  var clearThreshold = 0.5;
  var mask = image.select(qaBand).gte(clearThreshold);
  return image.updateMask(mask);
}

var filteredMasked = filteredS2WithCs
  .map(maskLowQA)
  .select('B.*');

var composite = filteredMasked.median();

// Отображение исходного композита
var rgbVis = {min: 0.0, max: 3000, bands: ['B4', 'B3', 'B2']};
Map.addLayer(composite.clip(geometry), rgbVis, 'RGB (Angarsk)');


// --- 2. ПОДГОТОВКА ТОЧЕК (GCPs) ---


var gcps = urban.map(function(f) { return f.set('landcover', 0); })
  .merge(bare.map(function(f) { return f.set('landcover', 1); }))
  .merge(water.map(function(f) { return f.set('landcover', 2); }))
  .merge(vegetation.map(function(f) { return f.set('landcover', 3); }));

// Добавляем случайную колонку для разделения данных
var gcps = gcps.randomColumn();

// Делим данные: 70% на обучение, 30% на валидацию
var split = 0.7; 
var trainingGcp = gcps.filter(ee.Filter.lt('random', split));
var validationGcp = gcps.filter(ee.Filter.gte('random', split));

// Сэмплинг для обучения
var training = composite.sampleRegions({
   collection: trainingGcp, 
   properties: ['landcover'], 
   scale: 10,
   tileScale: 16
});


// --- 3. ОБУЧЕНИЕ И КЛАССИФИКАЦИЯ ---

// Обучаем классификатор на trainingGcp
var classifier = ee.Classifier.smileRandomForest(50).train({
   features: training,  
   classProperty: 'landcover', 
   inputProperties: composite.bandNames()
});

// Классифицируем изображение
var classified = composite.classify(classifier);

// Палитра: Urban, Bare, Water, Vegetation
var palette = ['#cc6d8f', '#ffc107', '#1e88e5', '#004d40' ];

Map.addLayer(classified.clip(geometry), {min: 0, max: 3, palette: palette}, 'Classification Result');


// --- 4. ОЦЕНКА ТОЧНОСТИ (ACCURACY ASSESSMENT) ---

// Используем validationGcp для проверки точности
var test = classified.sampleRegions({
  collection: validationGcp,
  properties: ['landcover'],
  tileScale: 16,
  scale: 10,
});


var confusionMatrix = test.errorMatrix('landcover', 'classification');

print("Overall accuracy", confusionMatrix.accuracy());
print("Consumer's accuracy", confusionMatrix.consumersAccuracy());
print("Producer's accuracy", confusionMatrix.producersAccuracy());
print('Kappa statistic', confusionMatrix.kappa());


// ---- vegetation layer


var cityArea =  geometry.area()


var cityAreaSqKm = ee.Number(cityArea).divide(1e6).round();
print("angarsk layer area (km): ", cityAreaSqKm);

var vegetationMask = classified.eq(3).clip(geometry);;


Map.addLayer(vegetationMask, {min:0, max:1, palette: ['white', 'green']}, 'Green Cover');

var areaImage = vegetationMask.multiply(ee.Image.pixelArea());



var area = areaImage.reduceRegion({
  reducer: ee.Reducer.sum(),
  geometry: geometry,
  scale: 10,
  bestEffort:true,
  maxPixels: 1e10
});

var vegetationAreaSqKm = area.getNumber('classification').divide(1e6).round();
print("vegetation area (km): ", vegetationAreaSqKm);

// --- 5. КЛАСТЕРИЗАЦИЯ (UNSUPERVISED CLASSIFICATION) ---

// 1. Подготовка обучающей выборки для кластеризатора
var trainingForCluster = composite.clip(geometry).sample({
  region: geometry,
  scale: 10,
  numPixels: 5000
});

// 2. Обучение кластеризатора (K-Means)
var clusterer = ee.Clusterer.wekaKMeans(4).train(trainingForCluster);

// 3. Применение кластеризации
var clustered = composite.cluster(clusterer);

// 4. Визуализация
var clusteredRemapped = clustered.remap([0, 1, 2, 3], [3, 0, 1, 2]); 

Map.addLayer(clusteredRemapped.clip(geometry), {min: 0, max: 3, palette: palette}, 'Clustering Result');

// --- 6. ОЦЕНКА КАЧЕСТВА КЛАСТЕРИЗАЦИИ ---

var clusterTest = clusteredRemapped.sampleRegions({
  collection: validationGcp,
  properties: ['landcover'],
  scale: 10,
  tileScale: 16
});

// Создаем матрицу ошибок
var clusterConfusionMatrix = clusterTest.errorMatrix('landcover', 'remapped');

print('--- Метрики кластеризации ---');
print('Confusion Matrix (Clustering):', clusterConfusionMatrix);
print('Overall Accuracy (Clustering):', clusterConfusionMatrix.accuracy());
print('Kappa Statistic (Clustering):', clusterConfusionMatrix.kappa());
