from qgis.core import QgsGeometry, QgsPoint, QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem, \
    QgsCoordinateTransform, QgsCoordinateTransform, QgsPointXY
import json


def getVertices(layerid, featureid):
    """Acces to feature in QgsVectorLayer. Get data form feature and return verticles of geometry in JSON style file
    Get data from metadata column (if exists). Add value accuraty to points
    """

    project = QgsProject.instance()

    # check layerid & featureid - if not valid and not excist - terminate function, get geometry from feature
    layer = project.mapLayer(layerid)
    if layer is None:
        print('Layer not exists in project')
        return
    feature = layer.getFeature(featureid)
    if not feature.isValid():
        print('Feature not exists in layer')
        return
    if feature.geometry().isEmpty():
        print("Feature  don't have geometry")
        return
    geometry = feature.geometry()

    # if p not in params:
    #    self.writeResponse('f"{self.TR('missingUp'}){p}{self.TR('parameter')}" , 400)'

    # get crs project, layer, check if crs layer = crs project if no transform to project crs
    proj_crs = project.crs()
    layer_crs = layer.crs()
    wgs_crs = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    layer_crs2proj_crs = QgsCoordinateTransform(layer_crs, proj_crs, project)
    wgs_crs2proj_crs = QgsCoordinateTransform(wgs_crs, proj_crs, project)
    if layer_crs != proj_crs:
        geometry.transform(layer_crs2proj_crs)

    # get metadata from feature if exists - parse JSON, return list with QgsPoint with cq atribute
    metadata_points = []
    try:
        metadata = str(feature['metadata'])
    except KeyError:
        metadata = 'missing_metadata'
    try:
        metadata_json = json.loads(metadata)
        for feature in metadata_json:
            try:
                feature['lat'], feature['lon'], feature['accuracy']
            except KeyError:
                pass
            else:
                feature_pkt = QgsGeometry(QgsPoint(feature['lat'], feature['lon']))
                feature_pkt.transform(wgs_crs2proj_crs)
                feature_pkt = feature_pkt.asPoint()
                feature_pkt.cq = feature['accuracy']
                metadata_points.append(feature_pkt)
        print('metadata is valid json file')
    except json.decoder.JSONDecodeError:
        print('metadata is not valid json file')

    # auxiliary function for QgsPoint()
    def pointdata(geometry, numberpoint, metadata_points=[]):
        vertexdata = dict()
        vertexdata['id'] = numberpoint
        vertexdata['x'] = geometry.x()
        vertexdata['y'] = geometry.y()
        vertexdata['z'] = geometry.z()
        epsilon = 0.02  # epsilon accuracy
        pointxy = QgsPointXY(geometry)
        for metadatafeature in metadata_points:
            if pointxy.compare(metadatafeature, epsilon):
                vertexdata['cq'] = metadatafeature.cq
                break
            else:
                vertexdata['cq'] = None
        return vertexdata

    # auxiliary function for  QgsLine()
    def linedata(geometry, numberpoints, metadata_points=[]):
        linevertex = []
        for count, geom in enumerate(geometry, start=numberpoints):
            linevertex.append(pointdata(geom, count, metadata_points))
        if linevertex[0]['x'] == linevertex[-1]['x'] and linevertex[0]['y'] == linevertex[-1]['y']:
            del linevertex[-1]
        else:
            pass
        return linevertex

    # auxiliary function for QgsPolygon()
    def polygondata(geometry, numberpoints, metadata_points=[]):
        linevertex = []
        objectJson = linedata(geometry.exteriorRing(), numberpoints, metadata_points)
        linevertex.append(objectJson)
        numberpoints += len(objectJson)
        ring_count = geometry.numInteriorRings()
        for ring in [x for x in range(ring_count)]:
            objectJson = linedata(geometry.interiorRing(ring), numberpoints, metadata_points)
            linevertex.append(objectJson)
            numberpoints += len(objectJson)
        return linevertex, numberpoints

    # start work with geometry
    pointnumber = 1
    objectJson = []
    # geometry Point/PointZ
    if geometry.wkbType() in (1, 1001):
        objectJson = [pointdata(geometry.get(), pointnumber, metadata_points)]
    # geometry MultiPoint/MultiPointZ
    elif geometry.wkbType() in (4, 1004):
        for pointcount, geom in enumerate(geometry.get(), pointnumber):
            objectJson.append([pointdata(geom, pointcount, metadata_points)])
    # geometry Linestrng/LinestringZ
    elif geometry.wkbType() in (2, 1002):
        objectJson = linedata(geometry.get(), pointnumber, metadata_points)
    elif geometry.wkbType() in (5, 1005):
        for geom in geometry.get():
            # objectpart = []
            geompart = linedata(geom, pointnumber, metadata_points)
            pointnumber += len(geompart)
            objectJson.append(geompart)
    # geometry Polygon/PolygonZ
    elif geometry.wkbType() in (3, 1003):
        objectJson = (polygondata(geometry.get(), pointnumber, metadata_points))[0]
    # geometry MultiPolygon/MultiPolygonZ
    elif geometry.wkbType() in (6, 1006):
        for geom in geometry.get():
            # objectpart = []
            geompart, actnumber = polygondata(geom, pointnumber, metadata_points)
            pointnumber += actnumber
            objectJson.append(geompart)
    else:
        print('Not known geometry type')
        return
    return objectJson