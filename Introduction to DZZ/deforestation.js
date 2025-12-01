/**
 * Function to mask clouds using the Sentinel-2 QA band
 * @param {ee.Image} image Sentinel-2 image
 * @return {ee.Image} cloud masked Sentinel-2 image
 */
function maskS2clouds(image) {
    var qa = image.select('QA60');
  
    // Bits 10 and 11 are clouds and cirrus, respectively.
    var cloudBitMask = 1 << 10;
    var cirrusBitMask = 1 << 11;
  
    // Both flags should be set to zero, indicating clear conditions.
    var mask = qa.bitwiseAnd(cloudBitMask).eq(0)
        .and(qa.bitwiseAnd(cirrusBitMask).eq(0));
  
    return image.updateMask(mask).divide(10000);
  }
  
  // Load Sentinel-2 TOA reflectance data for Irkutsk
  var dataset2019 = ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
                    .filterDate('2019-06-01', '2019-09-15')
                    // Pre-filter to get less cloudy granules.
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                    .map(maskS2clouds).median();
  var dataset2020 = ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
                    .filterDate('2020-06-01', '2020-09-15')
                    // Pre-filter to get less cloudy granules.
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                    .map(maskS2clouds).median();
  var dataset2021 = ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
                    .filterDate('2021-06-01', '2021-09-15')
                    // Pre-filter to get less cloudy granules.
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                    .map(maskS2clouds).median();
                    
  var img = ee.Image([dataset2019.select('B4'),dataset2020.select('B3'),dataset2021.select('B2')]);
  var rgbVis = {
    min: 0.0,
    max: 0.3,
    bands: ['B4', 'B3', 'B2'],
  };
  
  // Irkutsk coordinates: latitude 52.2802, longitude 104.2747
  // Map.setCenter(104.2747, 52.2802, 12);
  Map.addLayer(img, rgbVis, 'RGB');
  