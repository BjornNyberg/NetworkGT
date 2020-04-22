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

import os,string,random,math,tempfile
import processing as st
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import *
from qgis.PyQt.QtGui import QIcon

class Thresholding(QgsProcessingAlgorithm):

    Raster = 'Raster'
    Method = 'Thresholding Method'
    inv = 'Invert Image'
    blocks = 'Block Size'
    adaptMethod = 'Adaptive Method'
    outRaster = 'Output Raster'
    blur = 'Modal Blurring'
    percent = 'Percent'

    def __init__(self):
        super().__init__()

    def name(self):
        return "Thresholding"

    def tr(self, text):
        return QCoreApplication.translate("Digitising", text)

    def displayName(self):
        return self.tr("Thresholding")

    def group(self):
        return self.tr("1. Digitising")

    def shortHelpString(self):
        return self.tr("Create a thresholded raster image based on the sci-kit package. Input requires a grayscale or RGB colored image. Three options are available 1. otsu, 2. adaptive thresholding and 3. percentile thresholding. Mode blurring will blur the resulting thresholded image by taking the mode value within the specified block size. \n 1. Otsu method will define fractures within the given image by calculating a global threshold that minimizes the intra-class variance of the rasters histogram values. If a block search radius is specified, the intra-class variance will be calcualted within the given search window. \n 2. Adaptive thresholding method will locally define a threshold that defines a fracture based on a guassian, median or mean value of pixels found within the given block search radius. \n 3. Percentile thresholding method will locally define a threshold cutoff based on the specified percentile and the rasters histogram values found within the given block search radius. \n Please refer to the help button for more information.")

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

        self.addParameter(QgsProcessingParameterEnum(self.Method,
                                self.tr('Select Thresholding Method'), options=[self.tr("otsu"),self.tr("adaptive"),self.tr("percentile")],defaultValue=0))

        self.addParameter(QgsProcessingParameterBoolean(self.inv, self.tr("Invert Image"),False))

        param1 = QgsProcessingParameterNumber(self.blocks,
                                self.tr('Block Size'), QgsProcessingParameterNumber.Double,0.0,minValue=0.0)
        param2 = QgsProcessingParameterEnum(self.adaptMethod,
                                self.tr('Adaptive Method'), options=[self.tr("gaussian"),self.tr("mean"),self.tr("median")],defaultValue=0)
        param3 = QgsProcessingParameterNumber(self.blur,
                                self.tr('Mode Blurring'), QgsProcessingParameterNumber.Double,1.0,minValue=0.0)
        param4 = QgsProcessingParameterNumber(self.percent,
                                self.tr('Percentile Threshold'), QgsProcessingParameterNumber.Double,0.05,minValue=0.001,maxValue=1.0)

        self.addParameter(QgsProcessingParameterRasterDestination(self.outRaster, self.tr("Output Raster"), None, False))

        param1.setFlags(param1.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param2.setFlags(param2.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param3.setFlags(param3.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        param4.setFlags(param4.flags() | QgsProcessingParameterDefinition.FlagAdvanced)

        self.addParameter(param1)
        self.addParameter(param2)
        self.addParameter(param4)
        self.addParameter(param3)

    def processAlgorithm(self, parameters, context, feedback):

        try:
            import networkx as nx
            from osgeo import gdal as osgdal
            from skimage.io import imread
            from skimage.color import rgb2gray
            from skimage.filters import threshold_local,threshold_otsu
            from skimage.util import invert
            from skimage.morphology import disk
            from skimage.filters.rank import modal, threshold_percentile, otsu
            from skimage.util import img_as_ubyte

        except Exception as e:
            feedback.reportError(QCoreApplication.translate('Error','%s'%(e)))
            feedback.reportError(QCoreApplication.translate('Error',' '))
            feedback.reportError(QCoreApplication.translate('Error','Error loading modules - please install the necessary dependencies'))
            return {}

        rlayer = self.parameterAsRasterLayer(parameters, self.Raster, context)
        inv = parameters[self.inv]
        block_size = parameters[self.blocks]
        adaptMethod = parameters[self.adaptMethod]
        mode = parameters[self.blur]
        method = parameters[self.Method]
        p = parameters[self.percent]

        aMethod = {0:"gaussian",1:"mean",2:"median"}

        outputRaster = self.parameterAsOutputLayer(parameters, self.outRaster, context)

        fname = ''.join(random.choice(string.ascii_lowercase) for i in range(10))

        outFname = os.path.join(tempfile.gettempdir(),'%s.tif'%(fname))
        rect = rlayer.extent()
        dp = rlayer.dataProvider()
        raster = dp.dataSourceUri()

        img = imread(raster)

        if dp.bandCount() == 1:
            grayscale = img
        else:
            try:
                grayscale = rgb2gray(img)
            except Exception as e:
                feedback.reportError(QCoreApplication.translate('Error',str(e)))
                feedback.reportError(QCoreApplication.translate('Error',' '))
                feedback.reportError(QCoreApplication.translate('Error','Failed to convert image from RGB to grayscale'))
                return {}

        if inv:
            grayscale = invert(grayscale)

        if block_size > 0 and block_size % 2 == 0:
            block_size += 1
            feedback.reportError(QCoreApplication.translate('Info','Warning: Algorithm requires an odd value for the block size parameter - selecting a value of %s'%(block_size)))

        nrows,ncols = grayscale.shape
        if method == 0:
            if block_size > 0:
                grayscale = img_as_ubyte(grayscale)
                thresh = otsu(grayscale,disk(block_size))
                binary = (grayscale < thresh).astype(float)
            else:
                thresh = threshold_otsu(grayscale)
                binary = (grayscale < thresh).astype(float)
        else:
            if block_size == 0.0:
                block_size = int((nrows*0.01)*(ncols*0.01))
                if block_size % 2 == 0:
                    block_size += 1
                feedback.pushInfo(QCoreApplication.translate('Info','Automatically selecting a block size of %s'%(block_size)))

            if method == 1:
                local_thresh = threshold_local(image=grayscale, block_size=block_size, method=aMethod[adaptMethod])
                binary = (grayscale < local_thresh).astype(float)
            else:
                thresh = threshold_percentile(grayscale,disk(block_size),p0=p)
                binary = (grayscale > thresh).astype(float)

        if mode > 0:
            binary = modal(binary, disk(mode))
            binary = (binary > 1).astype(float)

        xres = rlayer.rasterUnitsPerPixelX()
        yres = rlayer.rasterUnitsPerPixelY()

        driver = osgdal.GetDriverByName('GTiff')
        dataset = driver.Create(outputRaster, ncols, nrows, 1, osgdal.GDT_Float32,)

        dataset.SetGeoTransform((rect.xMinimum(),xres, 0, rect.yMaximum(), 0, -yres))

        wkt_prj = rlayer.crs().toWkt()
        dataset.SetProjection(wkt_prj)
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(0)
        band.WriteArray(binary)
        dataset,band = None,None

        return {self.outRaster:outputRaster}

if __name__ == '__main__':
    pass
