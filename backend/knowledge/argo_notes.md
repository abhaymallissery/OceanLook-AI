# FloatChat knowledge notes
Short notes written for FloatChat from the Argo User's Manual and the Argo data pages (argo.ucsd.edu/data). They are the only source used to answer concept questions. Check the official manual before quoting them in a paper.

## What Argo is
Argo is a global array of autonomous profiling floats. A float drifts at a parking depth (typically 1000 dbar), descends to about 2000 dbar, then rises to the surface while measuring pressure, temperature and salinity with a CTD sensor. At the surface it transmits the profile by satellite. A typical cycle lasts about 10 days, so one float gives roughly 36 profiles per year.

## Measured variables and units
Each profile has pressure (PRES, decibar), in-situ temperature (TEMP, degrees Celsius, ITS-90) and practical salinity (PSAL, PSU, practical salinity scale 1978). Variables with the suffix ADJUSTED hold values corrected in real time or in delayed mode. FloatChat uses the ADJUSTED values.

## Quality control flags
Every measurement has a QC flag. 0 means no QC was performed. 1 means good. 2 means probably good. 3 means probably bad but potentially correctable. 4 means bad. 5 means the value was changed. 8 means estimated. 9 means missing. FloatChat keeps only flag 1 for pressure and for the variable being analysed, which is the most conservative choice.

## Data modes
R means real-time data with automatic checks only. A means real-time data with adjustments applied. D means delayed-mode data that a scientist has examined and corrected, usually after about 12 months. Delayed-mode data are the most reliable for scientific statistics, so older years are better than the latest months.

## Pressure and depth
Argo measures pressure, not depth. Near the surface 1 dbar is very close to 1 metre, but the two drift apart with depth and latitude. FloatChat converts pressure to depth in metres with the UNESCO formula (Saunders, Fofonoff and Millard) so that a question about 500 m means 500 metres.

## Argo data centres and files
Argo data are served by two Global Data Assembly Centres (GDACs): Ifremer in France and USGODAE in the USA. Both hold identical NetCDF files in three folders: dac (sorted by data assembly centre), geo (sorted by ocean basin, year, month and day) and latest_data (most recent profiles). File names starting with R are real-time and D are delayed-mode. ERDDAP servers expose the same data as tables.

## How FloatChat calculates an answer
For every profile in the chosen region and period, FloatChat takes the good levels, converts pressure to depth, and linearly interpolates between the two levels around the requested depth. It never extrapolates and skips profiles whose surrounding levels are more than 100 m apart. The statistic (mean, median, minimum or maximum) is then taken across profiles, counting each profile once.

## Limits of the results
Results describe only the downloaded subset of Argo data. Regions are simple latitude and longitude boxes, so a box can include a little land or a neighbouring sea. Floats are not spread evenly, so a mean across profiles is not the same as an area-weighted ocean average. Profiles without usable adjusted values are left out.
