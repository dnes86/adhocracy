from pylons import request

from adhocracy.lib.base import BaseController
from adhocracy.lib.templating import render_json, render_geojson
from adhocracy.model import meta, Region

from sqlalchemy import func

import geojson
from shapely.wkb import loads
from shapely.geometry import Polygon, MultiPolygon, box

import logging
log = logging.getLogger(__name__)


USE_POSTGIS = 'USE_POSTGIS'
USE_SHAPELY = 'USE_SHAPELY'

BBOX_FILTER_TYPE = USE_POSTGIS
SIMPLIFY_TYPE = USE_SHAPELY

COMPLEXITY_TOLERANCE = {
    '0': 0.5,
    '1': 0.1,
    '2': 0.02,
    '3': 0.005,
    '4': 0.001
    }

class GeoController(BaseController):

    def get_boundaries_json(self):
        admin_level = request.params.get('admin_level')
        
        complexity = request.params.get('complexity')
        tolerance = COMPLEXITY_TOLERANCE[complexity]

        bbox = map(float, request.params.get('bbox').split(','))
        assert(len(bbox)==4)

        q = meta.Session.query(Region)
        q = q.filter(Region.admin_level == admin_level)

        if BBOX_FILTER_TYPE == USE_POSTGIS:
            q = q.filter(Region.boundary.intersects(func.setsrid(func.box2d('BOX(%f %f, %f %f)'%(tuple(bbox))), 4326)))

        if SIMPLIFY_TYPE == USE_POSTGIS:
            # NYI
            pass

        def make_feature(region):
            return dict(geometry = loads(str(region.boundary.geom_wkb)), properties = {'label': region.name, 'admin_level': region.admin_level})

        if BBOX_FILTER_TYPE == USE_SHAPELY:
            sbox = box(*bbox)
            regions = filter(lambda region: sbox.intersection(region['geometry']), map(make_feature, q.all()))

        elif BBOX_FILTER_TYPE == USE_POSTGIS:

            regions = map(make_feature, q.all())

        if SIMPLIFY_TYPE == USE_SHAPELY:

            def simplify_region(region):
                if region['geometry'].is_valid:
                    geom_simple = region['geometry'].simplify(tolerance, True)
                    if geom_simple.is_valid and geom_simple.area != 0:
                        region['geometry'] = geom_simple
                    else:
                        log.warn('invalid simplified geometry for %s'%region['properties']['label'])
                else:
                    log.warn('invalid geometry for %s'%region['properties']['label'])
                return region

            regions = map(simplify_region, regions)

        return render_geojson(geojson.FeatureCollection([geojson.Feature(**r) for r in regions]))
