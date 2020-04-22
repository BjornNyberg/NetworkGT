'''This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.'''

import os,string,random,math, tempfile
import processing as st
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import *
from qgis.PyQt.QtGui import QIcon

class Fracture_Network(QgsProcessingAlgorithm):

    Network='Network'
    Raster = 'Raster'
    #SkelMethod = 'Skeletonize Method'
    inv = 'Invert Image'
    distance = 'Simplify Distance'
    sdistance = 'Short Isolated Fractures'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Digitise Fracture Network"

    def tr(self, text):
        return QCoreApplication.translate("Digitising", text)

    def displayName(self):
        return self.tr("Digitise Fracture Network")

    def group(self):
        return self.tr("1. Digitising")

    def shortHelpString(self):
        return self.tr("Digitise a fracture network based on a binary image by thinning the raster (skeletonize) and subsequently converting to a linestring geometry with topologically consistent x node intersections. \n The 'Simplify Line Distance' parameter will apply a 'Douglas-Peucker' algorithm to simplify the linestring geometry within the user specified tolerance. The 'Short Isolated Fractures Threshold' will delete I - I branches that are smaller than the specified value. \n Please refer to the help button for more information.")

    def groupId(self):
        return "1. Digitising"

    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/wiki/1.-Digitising-Tools"

    def createInstance(self):
        return type(self)()

    def icon(self):
        n,path = 2,os.path.dirname(__file__)
        while(n):
            path=os.path.dirname(path)
            n -=1
        pluginPath = os.path.join(path,'icons')
        return QIcon( os.path.join( pluginPath, 'FM.jpg') )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.Raster,
            self.tr("Raster"), None, False))
        self.addParameter(QgsProcessingParameterVectorDestination(
            self.Network,
            self.tr("Network"),
            QgsProcessing.TypeVectorLine))

        self.addParameter(QgsProcessingParameterBoolean(self.inv, self.tr("Invert Binary Image"),False))

        # self.addParameter(QgsProcessingParameterEnum(self.SkelMethod,
        #                         self.tr('Select Skeletonize Method'), options=[self.tr("lee"),self.tr("medial axis")],defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(self.distance,
                                self.tr('Simplify Line Distance'), QgsProcessingParameterNumber.Double,0.0,optional=True,minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(self.sdistance,
                                self.tr('Short Isolated Fractures Threshold'), QgsProcessingParameterNumber.Double,0.0,optional=True,minValue=0.0))

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import networkx as nx
            from osgeo import gdal as osgdal
            from skimage.morphology import medial_axis, skeletonize
            from skimage.util import invert
            from skimage.io import imread
        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        rlayer = self.parameterAsRasterLayer(parameters, self.Raster, context)
        sMethod  = 0 #self.parameterAsInt(parameters, self.SkelMethod, context)
        distance = parameters[self.distance]
        sdistance = parameters[self.sdistance]
        inv = parameters[self.inv]

        fname = ''.join(random.choice(string.ascii_lowercase) for i in range(10))

        outFname = os.path.join(tempfile.gettempdir(),'%s.tif'%(fname))
        rect = rlayer.extent()
        dp = rlayer.dataProvider()
        raster = dp.dataSourceUri()

        xres = rlayer.rasterUnitsPerPixelX()
        yres = rlayer.rasterUnitsPerPixelY()

        img = imread(raster)
        stats = dp.bandStatistics(1,QgsRasterBandStats.All,rect,0)

        if dp.bandCount() != 1 or stats.maximumValue > 1:
            feedback.reportError(QCoreApplication.translate('Error','Tool requires a binary raster input - please run the Thresholding tool.'))
            return {}

        if inv:
            img = invert(img)

        nrows,ncols = img.shape

        if sMethod  == 0:
            skeleton = skeletonize(img, method='lee').astype(float)
        elif sMethod  == 1:
            skeleton = medial_axis(img).astype(float)

        driver = osgdal.GetDriverByName('GTiff')
        dataset = driver.Create(outFname, ncols, nrows, 1, osgdal.GDT_Float32,)

        dataset.SetGeoTransform((rect.xMinimum(),xres, 0, rect.yMaximum(), 0, -yres))

        wkt_prj = rlayer.crs().toWkt()
        dataset.SetProjection(wkt_prj)
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(0)
        band.WriteArray(skeleton)
        dataset,band = None,None

        outSHP = os.path.join(tempfile.gettempdir(),'%s.shp'%(fname))
        if distance > 0: #Vectorize - dissolve - simplify - split
            params = {'input':outFname,'type':0,'column':'value','-s':False,'-v':False,'-z':False,'-b':False,'-t':False,'output':outSHP,'GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_OUTPUT_TYPE_PARAMETER':2,'GRASS_VECTOR_DSCO':'','GRASS_VECTOR_LCO':'','GRASS_VECTOR_EXPORT_NOCAT':False}
            outSkel = st.run("grass7:r.to.vect",params,context=context,feedback=feedback)
            params = {'INPUT':outSkel['output'],'FIELD':[],'OUTPUT':'memory:'}
            outVector = st.run("native:dissolve",params,context=context,feedback=feedback)
            params = {'INPUT':outVector['OUTPUT'],'METHOD':0,'TOLERANCE':distance,'OUTPUT':'memory:'}
            templines = st.run("native:simplifygeometries",params,context=context,feedback=feedback)
            params = {'INPUT':templines['OUTPUT'],'LINES':templines['OUTPUT'],'OUTPUT':'memory:'}
            tempOut = st.run('native:splitwithlines',params,context=context,feedback=feedback)
        else: #Vectorize - split
            params = {'input':outFname,'type':0,'column':'value','-s':False,'-v':False,'-z':False,'-b':False,'-t':False,'output':outSHP,'GRASS_REGION_PARAMETER':None,'GRASS_REGION_CELLSIZE_PARAMETER':0,'GRASS_OUTPUT_TYPE_PARAMETER':2,'GRASS_VECTOR_DSCO':'','GRASS_VECTOR_LCO':'','GRASS_VECTOR_EXPORT_NOCAT':False}
            templines = st.run("grass7:r.to.vect",params,context=context,feedback=feedback)
            params = {'INPUT':templines['output'],'LINES':templines['output'],'OUTPUT':'memory:'}
            tempOut = st.run('native:splitwithlines',params,context=context,feedback=feedback)

        params = {'INPUT':tempOut['OUTPUT'],'OUTPUT':'memory:'}
        explodeOut = st.run("native:explodelines",params,context=context,feedback=feedback)

        G = nx.Graph()
        for feature in explodeOut['OUTPUT'].getFeatures(QgsFeatureRequest()):
            try:
                geom = feature.geometry().asPolyline()
                start,end = geom[0],geom[-1]
                startx,starty=start
                endx,endy=end
                length = feature.geometry().length()
                branch = [(startx,starty),(endx,endy)]
                G.add_edge(branch[0],branch[1],weight=length)
            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Node Error','%s'%(e)))

        fields = QgsFields()
        prj = QgsCoordinateReferenceSystem(wkt_prj)
        (writer, dest_id) = self.parameterAsSink(parameters, self.Network, context,
                                               fields, QgsWkbTypes.LineString, prj)
        fet = QgsFeature()
        skip_edges = []
        minD = xres*1.1

        for circle in nx.cycle_basis(G): #Fix x node intersections
            start,curDist,end2 = None,None,None
            cLen = len(circle)
            if cLen <= 4:
                skip = []
                for enum,end in enumerate(circle):
                    if G.degree(end) != 3:
                        cLen = -1
                    if start == None:
                        start = end
                        start1 = end
                        continue
                    elif enum == 1:
                        start2 = end
                    elif enum == 2:
                        end1 = end
                    else:
                        end2 = end

                    dx,dy = start[0]-end[0],start[1]-end[1]
                    dist = math.sqrt((dx**2)+(dy**2))
                    if curDist == None:
                        curDist = dist
                    if dist > minD or dist != curDist:
                        cLen == -1
                        break
                    curDist = dist
                    skip.extend([(start,end),(end,start)])
                    start = end
                if end2:
                    dx,dy = start[0]-start1[0],start[1]-start1[1]
                    dist = math.sqrt((dx**2)+(dy**2))
                    if dist > minD or dist != curDist:
                        cLen == -1
                    skip.extend([(start,start1),(start1,start)]) #Close circle

                    if cLen == 4:
                        skip_edges.extend(skip)
                        polylines = [[QgsPointXY(start1[0],start1[1]),QgsPointXY(end1[0],end1[1])],[QgsPointXY(start2[0],start2[1]),QgsPointXY(end2[0],end2[1])]]
                        for points in polylines:
                            outGeom = QgsGeometry.fromPolylineXY(points)
                            fet.setGeometry(outGeom)
                            writer.addFeature(fet,QgsFeatureSink.FastInsert)

        for edge in G.edges(data=True):
            if edge not in skip_edges:
                L = edge[2]['weight']
                start = edge[0]
                end = edge[1]
                vertices = [G.degree(start),G.degree(end)]
                if L < sdistance and sum(vertices) == 2:
                    continue
                points = [QgsPointXY(start[0],start[1]),QgsPointXY(end[0],end[1])]
                outGeom = QgsGeometry.fromPolylineXY(points)
                fet.setGeometry(outGeom)
                writer.addFeature(fet,QgsFeatureSink.FastInsert)

        return {self.Network:dest_id}

if __name__ == '__main__':
    pass
