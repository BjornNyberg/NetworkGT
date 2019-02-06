#==================================
#Author Bjorn Burr Nyberg 
#University of Bergen
#Contact bjorn.nyberg@uib.no
#Copyright 2016
#==================================

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

import ternary,sys,time,os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cmx
import matplotlib.colors as colors

def get_cmap(N):
    color_norm  = colors.Normalize(vmin=0, vmax=N-1)
    scalar_map = cmx.ScalarMappable(norm=color_norm, cmap='hsv') 
    def map_index_to_rgb_color(index):
        return scalar_map.to_rgba(index)
    return map_index_to_rgb_color


def main(xlsx):
    try:
        
        df = pd.read_excel(xlsx)
        os.remove(xlsx)
        
        x = df.X/df['No__Nodes']
        z = df.Y/df['No__Nodes']
        y = df.I/df['No__Nodes']
        data = zip(x,y,z)
        sample = ['Sample #%s'%(s) for s in df['Sample_No_']]
        scale = 1.0
        
        figure, tax = ternary.figure(scale=scale)
        ax = tax.get_axes()

        tax.boundary(linewidth=2.0)
        tax.gridlines(color="blue", multiple=0.1)

        tax.set_title("IYX Topology", fontsize=25)
        tax.left_axis_label("% Y", fontsize=20)
        tax.right_axis_label("% I", fontsize=20)
        tax.bottom_axis_label("% X", fontsize=20)

        p1s = [(0,0.75,0.25),(0, 0.66666, 0.33333),(0,0.562500,0.437500),(0,0.429,0.571),(0,0.2,0.8)]
        p2s = [(0.2, 0.8, 0),(0.273,0.727,0),(0.368,0.632,0),(0.5,0.5,0),(0.692,0.308,0)]
        text = [(1.0,0.65),(1.2,0.585),(1.4,0.495),(1.6,0.38),(1.8,0.2)]

        for p1, p2,t in zip(p1s,p2s,text):
            tax.line(p1, p2, linewidth=1., marker=None, color='gray', linestyle="-")
            ax.annotate(t[0], xy = (0.49,t[1]))

        #tax.ticks(ticks=[1,0.5,0,1,0.5,0,1,0.5,0],locations=[0,0.5,1,0,0.5,1,0,0.5,1],axis='lbr',linewidth=1)
        tax.ticks(axis='lbr')
        tax.clear_matplotlib_ticks()

        c = get_cmap(len(sample)+1)
        
        counter = 1
        for v,l in zip(data,sample):
            color = c(counter)
            counter += 1
            tax.scatter([v], marker='o', color=color, label=l,s=35)
            
        tax.legend(scatterpoints = 1)
        tax.clear_matplotlib_ticks()
        #tax.show()

        x = df['C___C']/df['No__Bran_1']
        z = df['C___I']/df['No__Bran_1']
        y = df['I___I']/df['No__Bran_1']
        data = zip(x,y,z)
        
        figure, tax = ternary.figure(scale=scale)
        ax = tax.get_axes()
        
        tax.boundary(linewidth=2.0)
        tax.gridlines(color="blue", multiple=0.1)

        tax.set_title("Branch Topology", fontsize=25)
        tax.left_axis_label("% C - I", fontsize=20)
        tax.right_axis_label("% I - I", fontsize=20)
        tax.bottom_axis_label("% C - C", fontsize=20)
        
        p = [(0,1,0),(0.01,0.81,0.18),(0.04,0.64,0.32),(0.09,0.49,0.42),(0.16,0.36,0.48),(0.25,0.25,0.5),
             (0.36,0.16,0.48),(0.49,0.09,0.42),(0.64,0.04,0.32),(0.81,0.01,0.18),(1,0,0)]

        text_loc = [(0.38,0.22),(0.446,0.145),(0.535,0.09),(0.656,0.042),(0.808,0.019)]
        text = ['1.0','1.2','1.4','1.6','1.8']

        for t,l in zip(text,text_loc):
            ax.annotate(t, xy = (l))
        
        tax.plot(p,linewidth=1., marker='o', color='gray', linestyle="-",markersize=3)

        #tax.ticks(ticks=[1,0.5,0,1,0.5,0,1,0.5,0],locations=[0,0.5,1,0,0.5,1,0,0.5,1],axis='lbr',linewidth=1)
        tax.ticks(axis='lbr')
        
        counter = 1
        for v,l in zip(data,sample):
            color = c(counter)
            counter += 1
            tax.scatter([v], marker='o', color=color, label=l,s=35)
            
        tax.legend(scatterpoints = 1)
        tax.clear_matplotlib_ticks()
        tax.show()    
                
    except Exception,e:
        print e
        time.sleep(10)

if __name__ == "__main__":
    
    try:
        xlsx =sys.argv[1]

        main(xlsx)
        
    except Exception,e:
        print e
        time.sleep(10)
