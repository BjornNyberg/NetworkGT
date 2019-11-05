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
    
import os, sys, math
import processing as st
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsField, QgsFeature, QgsPointXY,QgsSpatialIndex, QgsProcessingParameterFolderDestination, QgsProcessingParameterField, QgsProcessingParameterNumber, QgsProcessing,QgsWkbTypes, QgsGeometry, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource, QgsProcessingParameterFeatureSink,QgsProcessingParameterNumber,QgsFeatureSink,QgsFeatureRequest,QgsFields,QgsProperty,QgsVectorLayer)
from qgis.PyQt.QtGui import QIcon
from collections import OrderedDict

class LineFrequency(QgsProcessingAlgorithm):

    LG = 'Line Grid'
    Network = 'Fracture Network'
    LFD='Line Frequency Data'
    Weight = 'Weight Field'
    Group = "Groupby Field"
    outDir = "Output Folder"
    
    def __init__(self):
        super().__init__()
        
    def name(self):
        return "Line Frequency"

    def tr(self, text):
        return QCoreApplication.translate("Line_Grid", text)

    def displayName(self):
        return self.tr("Line Frequency")
 
    def group(self):
        return self.tr("Geometry")
    
    def shortHelpString(self):
        return self.tr("Create a Line Frequency sampling method")

    def groupId(self):
        return "Geometry"
    
    def helpUrl(self):
        return "https://github.com/BjornNyberg/NetworkGT/blob/master/QGIS/README.pdf"
    
    def createInstance(self):
        return type(self)()

    def icon(self):
        pluginPath = os.path.join(os.path.dirname(__file__),'icons')
        return QIcon( os.path.join( pluginPath, 'LF.jpg') )
    
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LG,
            self.tr("Line Grid"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.Network,
            self.tr("Fracture Network"),
            [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterField(self.Weight,
                                self.tr('Weight Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Numeric, optional=True))
        self.addParameter(QgsProcessingParameterField(self.Group,
                                self.tr('Group Field'), parentLayerParameterName=self.Network, type=QgsProcessingParameterField.Any, optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.LFD,
            self.tr("Line Frequency Data"),
            QgsProcessing.TypeVectorLine))
        self.addParameter(QgsProcessingParameterFolderDestination(self.outDir,
                self.tr('Directory Destination'), optional=True))
    
    def processAlgorithm(self, parameters, context, feedback):
        
        LG = self.parameterAsSource(parameters, self.LG, context)
        Network = self.parameterAsSource(parameters, self.Network, context)

        field_check = LG.fields().indexFromName('Sample_No_')
            
        if field_check == -1:
            editLayer = self.parameterAsLayer(parameters, self.LG, context)
            pr = editLayer.dataProvider()   
            pr.addAttributes([QgsField('Sample_No_', QVariant.Int)])
            editLayer.updateFields()
            f_len = len(editLayer.fields()) - 1
            editLayer.startEditing()                             
            for feature in editLayer.getFeatures():
                pr.changeAttributeValues({feature.id():{f_len:feature.id()}})
            editLayer.commitChanges()
            
        outDir = parameters[self.outDir]
        wF = parameters[self.Weight]
        gF = parameters[self.Group]

        index = QgsSpatialIndex(Network.getFeatures())
        orig_data = {feature.id():feature for feature in Network.getFeatures()}
        
        infc = parameters[self.LG]
        infc2 = parameters[self.Network]
        
        field_check = LG.fields().indexFromName('Sample_No_')
            
        if field_check == -1:            
            feedback.reportError(QCoreApplication.translate('Input Error','Add "Sample_No_" attribute field to Line Grid input file'))
            return {}
            
        fs = QgsFields()
        skip = ['Sample_No_','Count','Distance']
        fields = Network.fields()
        for field in fields:
            if field.name() not in skip:
                fs.append( QgsField(field.name() ,field.type() ))
                
        fs.append(QgsField('Sample_No_', QVariant.Int))
        fs.append(QgsField('Count', QVariant.Int))
        fs.append(QgsField('Distance', QVariant.Double))  
        
        (writer, dest_id) = self.parameterAsSink(parameters, self.LFD, context,
                                            fs, QgsWkbTypes.LineString, Network.sourceCrs())
                                            
        sources,edges,Lengths,k = {},{},{},{}
        for feature in LG.getFeatures():
            geom = feature.geometry()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = geom.asPolyline()
            else:
                geom = geom.asMultiPolyline()[0]
            x,y = geom[0]
            startx,starty=round(x,6), round(y,6)
            sources[feature['Sample_No_']] = (startx,starty)
        
        feedback.pushInfo(QCoreApplication.translate('TempFiles','Creating Line Frequency Sampling'))
        parameters = {'INPUT':infc,'LINES':infc2,'OUTPUT':'memory:'}  
        templines = st.run('native:splitwithlines',parameters,context=context,feedback=feedback)   
        
        for feature in templines['OUTPUT'].getFeatures():
            geom = feature.geometry()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = geom.asPolyline()
            else:
                geom = geom.asMultiPolyline()[0]
            start,end = geom[0],geom[-1]
            startx,starty=start
            endx,endy=end

            pnts1,pnts2 = [(round(startx,6),round(starty,6)),(round(endx,6),round(endy,6))]     
            Length = feature.geometry().length()
            ID = feature['Sample_No_']

            if ID in edges:
                edges[ID].add_edge(pnts1,pnts2,weight=Length)
            else:
                G = nx.Graph()
                G.add_edge(pnts1,pnts2,weight=Length)
                edges[ID] = G
        
        fet = QgsFeature() 
        SN, SS, D, W = [],[],[],[]
        output = os.path.exists(outDir)
        for feature in templines['OUTPUT'].getFeatures():
            geom = feature.geometry()
            if QgsWkbTypes.isSingleType(geom.wkbType()):
                geom = geom.asPolyline()
            else:
                geom = geom.asMultiPolyline()[0]
            start,end = geom[0],geom[-1]
            startx,starty=start
            endx,endy=end

            startx,starty = (round(startx,6),round(starty,6))
            endx, endy = (round(endx,6),round(endy,6))  
            
            ID = feature['Sample_No_']

            if ID not in Lengths:
                G = edges[ID]
                if len(G.nodes()) > 2:
                    source = sources[ID]
                    length,path = nx.single_source_dijkstra(G,source,weight='weight')
                    Lengths[ID] = length
                    k[ID] = list(length.keys())
            c, L = -1,-1
            if ID in Lengths:
                try:
                    c = k[ID].index((endx,endy))
                    L = Lengths[ID][(endx,endy)]
                except Exception as e:
                    pass
                featFIDs = index.nearestNeighbor(QgsPointXY(endx,endy), 1)    
                
                d = 1e10
                for FID in featFIDs:
                    feature2 = orig_data[FID]
                    testGeom = QgsGeometry.fromPointXY(QgsPointXY(endx,endy))
                    dist = QgsGeometry.distance(testGeom,feature2.geometry())

                    if dist < d:
                        rows = []
                        for field in fields:
                            if field.name() not in skip:
                                rows.append(feature2[field.name()])
                            if field.name() == wF:
                                wFv = feature2[field.name()]
                            elif field.name() == gF:
                                gFv = feature2[field.name()]
                        d = dist
                            
                rows.extend([ID,c,L])        
                fet.setGeometry(feature.geometry())
                
                fet.setAttributes(rows)
                if output:
                    SN.append(ID)
                    D.append(L)
                    if gF:
                        SS.append(str(gFv))
                    else:
                        SS.append('Total')
                    if wF:
                        W.append(float(wFv))
                    else:
                        W.append(float(c))

                writer.addFeature(fet,QgsFeatureSink.FastInsert)    
     
        del sources,edges,Lengths,k
        if output:
            try:
                feedback.pushInfo(QCoreApplication.translate('TempFiles','Creating Output Files to %s'%(outDir)))
                data = pd.DataFrame({0:SN, 1:SS, 2:D, 3:W})
                data.dropna(inplace=True)
                #fig = plt.figure()
                columns = list(data.columns.values)
                outValues = {}
                for n,df in data.groupby(0):

                    if len(df) > 1:

                        #ax = fig.add_subplot(1,1,1)
                        data = {}
                        vf_values = {}
             
                        max_dist = max(df[2])

                        x,y,c = [0],[0],0.0
                        values = df.sort_values(2)

                        prev = 0
                        for x_value,disp in zip(values[2],values[3]):
                            y.append(y[-1])
                            c += disp
                            y.append(c)
                            x.extend([x_value,x_value])
                            spacing = [x_value - prev]
                            prev = x_value
                                
                            if 'Total' not in data:
                                data['Total'] = spacing
                            else:
                                spacing_data = data['Total']                            
                                spacing += spacing_data
                                data['Total'] = spacing

                        m = float(max(y)/max_dist)

                        for x_v,y_v in zip(x,y):
                            test_y = x_v*m
                            vf = [y_v/float(y[-1]) - test_y/y[-1]]
                            if 'Total' in vf_values:
                                vf_data = vf_values['Total']
                                vf_data += vf
                                vf_values['Total'] = vf_data
                            else:
                                vf_values['Total'] = vf
                                
                        x.append(max_dist)
                        y.append(y[-1])
                        #ax.plot(x,y,label='Total')
                        
                        for n2,g in df.groupby(1):
                            if n2 != 'Total':
                                x,y,c = [0],[0],0.0
                                values = g.sort_values(2)
                                
                                prev = 0
                                for x_value,disp in zip(values[2],values[3]):

                                    y.append(y[-1])
                                    c += disp
                                    y.append(c)
                                    x.extend([x_value,x_value])
                                    spacing = [x_value - prev]
                                    prev = x_value
                                    
                                    if n2 not in data:
                                        data[n2] = spacing
                                        
                                    else:
                                        spacing_data = data[n2]                            
                                        spacing += spacing_data
                                        data[n2] = spacing
                                        
                                m = float(max(y)/max_dist)
                                for x_v,y_v in zip(x,y):
                                    test_y = x_v*m
                                    vf = [y_v/float(y[-1]) - test_y/float(y[-1])]

                                    if n2 in vf_values:
                                        vf_data = vf_values[n2]
                                        vf_data += vf
                                        vf_values[n2] = vf_data
                                    else:
                                        vf_values[n2] = vf
                                #ax.plot(x,y,label='%s'%(n2))        
                                
                        #ylim = max(y)+max(y)*0.1        
                        #ax.set_xlim([0,max_dist+max_dist*0.01])
                        #ax.set_ylim([0,ylim])
                        #ax.set_title('Cumulative Frequency')
                        #ax.set_xlabel('Distance')
                        #ax.set_ylabel('Frequency')
                        #ax.legend(loc=2,title='Legend',fancybox=True,fontsize=8)

                        #output = r'D:\Temp\%s.svg'%(n)
                        #fig.savefig(output)
                        #plt.clf()
                        data = OrderedDict(sorted(data.items()))
                        
                        for k,v in data.items():
                            if k not in outValues:
                                table_vals = [[],[],[],[],[],[],[],[],[],[],[],[],[]]
                            else:
                                table_vals = outValues[k]
                            table_vals[0].append(n)
                            table_vals[1].append(len(v))
                            table_vals[2].append(round(np.mean(v),2))
                            table_vals[3].append(round(np.std(v),2))
                            table_vals[4].append(round(min(v),2))
                            table_vals[5].append(round(np.percentile(v, 25),2))
                            table_vals[6].append(round(np.percentile(v, 50),2))
                            table_vals[7].append(round(np.percentile(v, 75),2))                  
                            table_vals[8].append(round(max(v),2))
                            table_vals[9].append(round(np.std(v)/np.mean(v),2))
                            outValues[k] = table_vals
                            
                        for k,vf in vf_values.items():
                            table_vals = outValues[k]
                            table_vals[10].append(round(max(vf),2))
                            table_vals[11].append(round(min(vf),2))
                            table_vals[12].append(round(math.fabs(max(vf))+ math.fabs(min(vf)),2))
                            outValues[k] = table_vals
                        
                row_labels = ['Sample_No_','Count','mean','std','min','25%','50%','75%','Max','CoV',r'D+',r'D-','Vf']
                for k,v in outValues.items():
                    output=r'D:\Temp\%s.csv'%(k)
                    outdf = pd.DataFrame(dict(zip(row_labels,table_vals)))
                    outdf.to_csv(output)
                    
            except Exception as e:
                feedback.pushInfo(QCoreApplication.translate('TempFiles','%s'%(e)))

        return {self.LFD:dest_id}
