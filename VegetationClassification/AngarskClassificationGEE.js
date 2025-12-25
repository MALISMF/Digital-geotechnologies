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

// Делим данные: 70% на обучение, 30% на валидацию (тест)
var split = 0.7; 
var trainingGcp = gcps.filter(ee.Filter.lt('random', split));
var validationGcp = gcps.filter(ee.Filter.gte('random', split));

// Сэмплинг (извлечение значений пикселей) для обучения
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

// Создаем матрицу ошибок (Confusion Matrix)
// Сравниваем 'landcover' (истина) с 'classification' (предсказание)
var confusionMatrix = test.errorMatrix('landcover', 'classification');


// Calculate overall accuracy.
print("Overall accuracy", confusionMatrix.accuracy());

// Calculate consumer's accuracy, also known as user's accuracy or
// specificity and the complement of commission error (1 − commission error).
print("Consumer's accuracy", confusionMatrix.consumersAccuracy());

// Calculate producer's accuracy, also known as sensitivity and the
// compliment of omission error (1 − omission error).
print("Producer's accuracy", confusionMatrix.producersAccuracy());

// Calculate kappa statistic.
print('Kappa statistic', confusionMatrix.kappa());