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
    
import  os,sys, time,math
from pylab import *
import numpy as np
import matplotlib as mpl
import pandas as pd
import collections

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon

from qgis.core import (edit,QgsField, QgsFeature, QgsPointXY,QgsProcessingParameterField,QgsProcessingParameterBoolean, QgsProcessingParameterNumber,QgsProcessingParameterFolderDestination,
QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,QgsWkbTypes,QgsFeatureSink,
QgsProcessingParameterNumber,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer,QgsProcessingParameterFeatureSink)


class RoseDiagrams(QgsProcessingAlgorithm):

    FN = 'Fracture Network'
    Bins = 'Bins'
    Weight = 'Field'
    Group = "Group"
    outDir = "Output Folder"
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Rose Diagram"

    def tr(self, text):
        return QCoreApplication.translate("Rose Diagram", text)

    def displayName(self):
        return self.tr("Rose Diagram")
 
    def group(self):
        return self.tr("Geometry")
    
    def shortHelpString(self):
        return self.tr("Create Weighted Rose Diagram Plots")

    def groupId(self):
        return "Geometry"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/blob/master/QGIS/README.pdf"
    
    def createInstance(self):
        return type(self)()

    def icon(self):
        pluginPath = os.path.join(os.path.dirname(__file__),'icons')
        return QIcon( os.path.join( pluginPath, 'RD.jpg') )
    
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.FN,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterNumber(
            self.Bins,
            self.tr("Rose Diagram Bin Size"),
            QgsProcessingParameterNumber.Double,
            10.0))
        self.addParameter(QgsProcessingParameterField(self.Weight,
                                self.tr('Weight Field'), parentLayerParameterName=self.FN, type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterField(self.Group,
                                self.tr('Group Field'), parentLayerParameterName=self.FN, type=QgsProcessingParameterField.Any))
        self.addParameter(QgsProcessingParameterFolderDestination(self.outDir,
                                self.tr('Figure Destination')))


    def processAlgorithm(self, parameters, context, feedback):
            
        FN = self.parameterAsSource(parameters, self.FN, context)
        WF = self.parameterAsString(parameters, self.Weight, context)
        G = self.parameterAsString(parameters, self.Group, context)
        bins = parameters[self.Bins]
        directory = self.parameterAsString(parameters, self.outDir, context)
        
        feedback.pushInfo(QCoreApplication.translate('RoseDiagram','Reading Data'))
        
        data = {}
        
        for feature in FN.getFeatures():
            ID = feature[G]

            geom = feature.geometry().asPolyline()
            start,end = geom[0],geom[-1]
            startx,starty=start
            endx,endy=end

            dx = endx - startx
            dy =  endy - starty

            angle = math.degrees(math.atan2(dy,dx))
            Bearing = (90.0 - angle) % 360
            if Bearing >= 180:
                Bearing -= 180
            
            if ID in data:
                data[ID].append((Bearing,feature[WF]))
            else:
                data[ID] = [(Bearing,feature[WF])]
                      
        bins = float(bins)
        counts = dict.fromkeys(np.arange(bins,360+bins,bins),0)
        counts = collections.OrderedDict(sorted(counts.items()))
        feedback.pushInfo(QCoreApplication.translate('RoseDiagram','Processing Data'))
        for k,v in data.items():
            x,y =[],[]
            name = 'Sample #%s'%(k)
            fig = figure(name)
            output = os.path.join(directory,name+'.svg')
            ax = fig.add_subplot(111, polar = True)

            num_values = []
  
            for num in v: #Get the reciprocal of the angle

                if num[0] == 0.0 or num[0] == 180.0:
                    num1 = 0.001  
                else:
                    num1 = num[0]
                
                if num1 <= 180:
                    num2 = num1 + 180
                else:
                    num2 = num1 - 180

                k1 = int(math.ceil(num1 / bins)) * bins

                k2 = int(math.ceil(num2 / bins)) * bins
                counts[k1] += num[1] #Length weighted polar plot
                counts[k2] += num[1]
                num_values.append(num[1])
            num_sum = sum(num_values)
            num_count = len(num_values)

            if num_sum != num_count:   
                max_num_values = max(num_values)
                num_values = [round((n*10000.0)/max_num_values,0) for n in num_values]
                num_records = len(num_values)*10
                m = 10000/(num_sum/num_records)
                          
            for num in v: #Get ~ mean vector data

                if num[0] == 0.0 or num[0] == 180.0:
                    num1 = 0.001  
                else:
                    num1 = num[0]
                
                if num1 <= 180:
                    num2 = num1 + 180
                    if num1 <= 90:
                        mnum = num1
                    else:
                        mnum = num1 + 180

                else:
                    num2 = num1 - 180
                    
                    if num1 > 270:
                        mnum = num1
                    else:
                        mnum = num2
                        
                if num_sum != num_count: 
                    multiplier = 1#int(round((num[1]*m)/max_num_values,0))
                else:
                    multiplier = 1
    
                x.extend([math.cos(math.radians(mnum))]*multiplier)
                y.extend([math.sin(math.radians(mnum))]*multiplier)

            v1 = np.mean(x)
            v2 = np.mean(y)

            if v2 < 0:
                mean = 180 - math.fabs(np.around(math.degrees(math.atan2(v2,v1)),decimals=2))
            else:
                mean = np.around(math.degrees(math.atan2(v2,v1)),decimals = 2)
       
            del x,y,v1,v2
     
            bins_data = [b - (bins/2.0) for b in counts.keys()]

            mode = max(counts, key=counts.get)

            if mode > 180:
                mode =- 180

            counts = list(counts.values())
            
            ax.text(-0.2,-0.05, 'Bin Size: %s$^\circ$\nBin Mode: %s - %s$^\circ$'%(bins,mode - bins, mode),verticalalignment='bottom', horizontalalignment='left',transform=ax.transAxes, fontsize=14)
            ax.text(1.25, -0.05, 'Mean: %s$^\circ$\nn=%s'%(mean,len(v)),verticalalignment='bottom', horizontalalignment='right',transform=ax.transAxes, fontsize=14)
            
            radians = [math.radians(i)for i in bins_data]
            counts=[(float(i)/sum(counts))*100 for i in counts]
            bin_r = math.radians(bins)

            
            bars = ax.bar(radians,counts, width=bin_r, align='center')        
            ax.set_theta_zero_location("N")
            ax.set_theta_direction(-1)
            
            s = round((max(counts)/5.0),0)
            if s == 0.0:
                s = (max(counts)/5.0)
                
            ticks = np.arange(0,s*6,s)     
            ax.set_yticks(ticks)
            thetaticks = np.arange(0,360,15)
            ax.set_thetagrids(thetaticks)

            for r, bar in zip(counts, bars):
                bar.set_facecolor(cm.Greys(r / max(counts)))
                bar.set_alpha(0.5)

            ax_1 = fig.add_axes([0.935, 0.1, 0.03, 0.2])        
            cmap = cm.Greys
            norm = mpl.colors.Normalize(vmin=0,vmax=max(counts))
            
            cb1 = mpl.colorbar.ColorbarBase(ax_1, cmap=cmap,norm=norm,alpha=0.5,ticks=ticks,orientation='vertical')
            cb1.ax.tick_params(labelsize=10)

            savefig(output)
        return {}
