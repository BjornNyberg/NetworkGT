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


import  os,sys, time,math
from pylab import *
import numpy as np
import matplotlib as mpl
import pandas as pd
import collections


def main (data,bins):

    try:

        df = pd.read_csv(data,header=None,sep=':',index_col=0)
        os.remove(data)
        bins = float(eval(bins))
    
        for k,values in df.iterrows():
            
            v = eval(values[1])
            x,y =[],[]
      
            fig = figure('Sample #%s'%(k))
            
            counts = dict.fromkeys(np.arange(bins,360+bins,bins),0)
            counts = collections.OrderedDict(sorted(counts.items()))

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
                    multiplier = int(round((num[1]*m)/max_num_values,0))
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

            counts = counts.values()
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
            ax.set_thetagrids(thetaticks, frac=1.165)

            for r, bar in zip(counts, bars):
                bar.set_facecolor(cm.Greys(r / max(counts)))
                bar.set_alpha(0.5)

            ax_1 = fig.add_axes([0.935, 0.1, 0.03, 0.2])        
            cmap = cm.Greys
            norm = mpl.colors.Normalize(vmin=0,vmax=max(counts))
            
            cb1 = mpl.colorbar.ColorbarBase(ax_1, cmap=cmap,norm=norm,alpha=0.5,ticks=ticks,orientation='vertical')
            cb1.ax.tick_params(labelsize=10)
        
            show()
            
    except Exception,e:
        print e
        time.sleep(10)

if __name__ == "__main__":        
    ###Inputs###
        
    data = sys.argv[1]
    bins = sys.argv[2]

    main(data,bins)
    

