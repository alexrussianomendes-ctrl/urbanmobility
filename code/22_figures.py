"""Figures: per-city maps (Walk, Transit, Bike in the Walk Score bands, populated 250 m cells of the urban centre
and the municipality), a dot plot of city means with 95% intervals per index and geography, and the population
share in each band per city. Reads results/cells/*.parquet, results/city_scores.csv.
Output: results/maps/<city>.png, results/fig_means_<geography>.png, results/fig_bands_<geography>.png"""
import os, sys, numpy as np, pandas as pd, geopandas as gpd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
B=__import__('os').environ.get('MS_BASE','.')
BANDS=[0,25,50,70,90,100.01]; LAB=['0-24','25-49','50-69','70-89','90-100']
COL=['#cde2fb','#86b6ef','#3987e5','#1c5cab','#0d366b']   # one hue, light->dark (ordinal)
cmap=ListedColormap(COL); norm=BoundaryNorm(BANDS,cmap.N)
INK='#2b2b2b'; MUTED='#6b6b6b'; GRID='#e4e3df'
NAME={'london':'Londres','berlin':'Berlim','nyc':'Nova York','chicago':'Chicago','losangeles':'Los Angeles','paris':'Paris','munich':'Munique','vienna':'Viena','lisbon':'Lisboa',
      'amsterdam':'Amsterdã','madrid':'Madri','barcelona':'Barcelona','milan':'Milão','rome':'Roma','moscow':'Moscou','stpetersburg':'São Petersburgo',
      'tokyo':'Tóquio','osaka':'Osaka','shanghai':'Xangai','beijing':'Pequim','shenzhen':'Shenzhen'}
IX={'walk':'Walk','transit_main':'Transit','bike':'Bike'}
plt.rcParams.update({'font.size':9,'text.color':INK,'axes.labelcolor':INK,'xtick.color':MUTED,'ytick.color':MUTED,'axes.edgecolor':GRID})
os.makedirs(f'{B}/results/maps',exist_ok=True)
only=sys.argv[1:] or list(NAME)
for c in only:
    f=f'{B}/results/cells/{c}_cells.parquet'
    if not os.path.exists(f): continue
    G=gpd.read_parquet(f); G=G[(G['pop']>0)&(G.in_uc|G.in_muni)]
    utm=G.estimate_utm_crs(); G=G.to_crs(utm)
    SA=f'{B}/data/study_areas'
    muni=gpd.read_file(f'{SA}/{c}_municipal.gpkg').to_crs(utm).boundary if os.path.exists(f'{SA}/{c}_municipal.gpkg') else G[G.in_muni].dissolve().boundary
    uc=gpd.read_file(f'{SA}/{c}_urban_centre.gpkg').to_crs(utm).boundary if os.path.exists(f'{SA}/{c}_urban_centre.gpkg') else G[G.in_uc].dissolve().boundary
    bx=G.total_bounds
    fig,axs=plt.subplots(1,3,figsize=(13,4.8),constrained_layout=True)
    for ax,(col,nm) in zip(axs,IX.items()):
        if col not in G or G[col].isna().all(): ax.set_axis_off(); ax.set_title(f'{nm}: sem dados'); continue
        G.plot(column=col,cmap=cmap,norm=norm,ax=ax,linewidth=0)
        uc.plot(ax=ax,color='white',linewidth=1.6); uc.plot(ax=ax,color=MUTED,linewidth=0.6,linestyle='--'); muni.plot(ax=ax,color='white',linewidth=1.8); muni.plot(ax=ax,color='#c2410c',linewidth=0.7)
        ax.set_xlim(bx[0]-1000,bx[2]+1000); ax.set_ylim(bx[1]-1000,bx[3]+1000); ax.set_aspect('equal')
        ax.set_title(nm,loc='left',fontsize=11); ax.set_axis_off()
        x0,x1=ax.get_xlim(); y0,_=ax.get_ylim(); L=10000 if (x1-x0)>40000 else 5000
        ax.plot([x0+0.04*(x1-x0),x0+0.04*(x1-x0)+L],[y0+0.03*(x1-x0)]*2,color=INK,lw=2); ax.text(x0+0.04*(x1-x0)+L/2,y0+0.045*(x1-x0),f'{L//1000} km',ha='center',fontsize=8)
    tv=G.transit_variant.iloc[0] if 'transit_variant' in G else ''
    h=[Patch(color=k,label=l) for k,l in zip(COL,LAB)]+[plt.Line2D([],[],color='#c2410c',lw=0.8,label='município'),plt.Line2D([],[],color=MUTED,lw=0.8,ls='--',label='centro urbano')]
    fig.legend(handles=h,loc='lower center',ncol=7,frameon=False,bbox_to_anchor=(0.5,-0.06))
    fig.suptitle(f'{NAME[c]}: notas estimadas em células de 250 m com população (Transit: {tv})',x=0.01,ha='left',fontsize=12)
    fig.savefig(f'{B}/results/maps/{c}.png',dpi=130,bbox_inches='tight'); plt.close(fig); print(c,'map')
D=pd.read_csv(f'{B}/results/city_scores.csv')
for geo,gl in (('municipality','município'),('urban_centre','centro urbano')):
    d=D[D.geography==geo].set_index('city')
    fig,axs=plt.subplots(1,3,figsize=(13,6.2),sharey=False,constrained_layout=True)
    for ax,k in zip(axs,('walk','transit','bike')):
        x=d[[f'{k}_mean',f'{k}_hw95']].dropna().sort_values(f'{k}_mean'); y=np.arange(len(x))
        ax.hlines(y,x[f'{k}_mean']-x[f'{k}_hw95'],np.minimum(x[f'{k}_mean']+x[f'{k}_hw95'],100),color='#86b6ef',lw=3)
        ax.plot(x[f'{k}_mean'],y,'o',color='#1c5cab',ms=6,mec='white',mew=1.5)
        ax.set_yticks(y); ax.set_yticklabels([NAME[i] for i in x.index]); ax.set_xlim(0,100); ax.set_xticks([0,25,50,70,90,100])
        for b in (25,50,70,90): ax.axvline(b,color=GRID,lw=0.8,zorder=0)
        ax.set_title(k.capitalize()+' Score',loc='left',fontsize=11); ax.tick_params(length=0)
        for s in ('top','right','left'): ax.spines[s].set_visible(False)
    fig.suptitle(f'Média ponderada por população ({gl}) e intervalo de 95% da validação',x=0.01,ha='left',fontsize=12)
    fig.text(0.01,-0.03,'Xangai, Pequim e Shenzhen: Walk Score é limite inferior (poucos destinos mapeados). Transit sem horários oficiais (Osaka, China; parte de Tóquio, São Petersburgo e Moscou): intervalo largo e tendência a subestimar.',fontsize=8,color=MUTED,ha='left')
    fig.savefig(f'{B}/results/fig_means_{geo}.png',dpi=130,bbox_inches='tight'); plt.close(fig)
    fig,axs=plt.subplots(1,3,figsize=(13,6.2),constrained_layout=True)
    for ax,k in zip(axs,('walk','transit','bike')):
        cols=[f'{k}_share_{s}' for s in ('lt25','25_49','50_69','ge70')]
        x=d[cols+[f'{k}_mean']].dropna().sort_values(f'{k}_mean'); y=np.arange(len(x)); left=np.zeros(len(x))
        for cc,colr,l in zip(cols,['#cde2fb','#86b6ef','#3987e5','#104281'],['<25','25-49','50-69','70+']):
            ax.barh(y,x[cc]*100,left=left,color=colr,height=0.7,edgecolor='white',linewidth=1,label=l); left+=x[cc].values*100
        ax.set_yticks(y); ax.set_yticklabels([NAME[i] for i in x.index]); ax.set_xlim(0,100); ax.set_xlabel('% da população')
        ax.set_title(k.capitalize()+' Score',loc='left',fontsize=11); ax.tick_params(length=0)
        for s in ('top','right','left'): ax.spines[s].set_visible(False)
    h,l=axs[0].get_legend_handles_labels(); fig.legend(h,l,loc='lower center',ncol=4,frameon=False,bbox_to_anchor=(0.5,-0.04))
    fig.suptitle(f'População por faixa de nota ({gl})',x=0.01,ha='left',fontsize=12)
    fig.savefig(f'{B}/results/fig_bands_{geo}.png',dpi=130,bbox_inches='tight'); plt.close(fig)
print('figures ok')
