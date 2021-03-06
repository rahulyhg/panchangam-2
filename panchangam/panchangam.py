#!/usr/bin/python3
#  -*- coding: utf-8 -*-

import sys

from datetime import datetime, date, timedelta
from pytz import timezone as tz
from icalendar import Calendar, Event, Alarm
from helper_functions import swe, MAX_SZ, MAX_DAYS, NAMES,\
    tr, get_solar_month_day, get_ekadashi_name, get_angam_data, time,\
    TITHI, NAKSHATRAM, SOLAR_MONTH, SOLAR_NAKSH, brentq, get_angam_float
from helper_functions import *
# from festival_rules import festival_rules


class panchangam:

    """This class enables the construction of a panchangam
    """

    def __init__(self, city, year=2012, script='deva', fmt='hh:mm'):
        """Constructor for the panchangam.
        """
        self.city = city
        self.year = year
        self.script = script
        self.fmt = fmt

        self.jd_start = swe.julday(year, 1, 1, 0)  # - tz_off/24.0

        self.weekday_start = swe.day_of_week(swe.julday(year, 1, 1)) + 1
        # swe has Mon = 0, non-intuitively!

        swe.set_sid_mode(swe.SIDM_LAHIRI)  # Force Lahiri Ayanamsha

    def computeAngams(self, computeLagnams=True):
        """Compute the entire panchangam
        """

        # INITIALISE VARIABLES
        self.jd_sunrise = [None] * MAX_SZ
        self.jd_sunset = [None] * MAX_SZ
        self.jd_moonrise = [None] * MAX_SZ
        self.jd_moonset = [None] * MAX_SZ
        self.solar_month = [None] * MAX_SZ
        self.solar_month_day = [None] * MAX_SZ

        solar_month_sunrise = [None] * MAX_SZ

        self.lunar_month = [None] * MAX_SZ
        self.month_data = [None] * MAX_SZ
        self.tithi_data = [None] * MAX_SZ
        self.tithi_sunrise = [None] * MAX_SZ
        self.nakshatram_data = [None] * MAX_SZ
        self.nakshatram_sunrise = [None] * MAX_SZ
        self.yogam_data = [None] * MAX_SZ
        self.karanam_data = [None] * MAX_SZ
        self.rashi_data = [None] * MAX_SZ
        self.lagna_data = [None] * MAX_SZ

        self.weekday = [None] * MAX_SZ
        self.kalams = [dict() for _x in range(MAX_SZ)]

        self.fest_days = {}
        self.festivals = [[] for _x in range(MAX_SZ)]

        # Computing solar month details for Dec 31
        # rather than Jan 1, since we have an always increment
        # solar_month_day at the start of the loop across every day in
        # year
        [self.solar_month[1], solar_month_day] = get_solar_month_day(self.jd_start - 1, self.city)

        if self.solar_month[1] != 9:
            raise(ValueError('Dec 31 does not appear to be Dhanurmasa!'))

        month_start_after_sunset = False

        #############################################################
        # Compute all parameters -- sun/moon latitude/longitude etc #
        #############################################################

        for d in range(MAX_SZ):
            self.weekday[d] = (self.weekday_start + d - 1) % 7

        for d in range(-1, MAX_DAYS + 1):
            [y, m, dt, t] = swe.revjul(self.jd_start + d - 1)

            # checking @ 6am local - can we do any better?
            local_time = tz(self.city.timezone).localize(datetime(y, m, dt, 6, 0, 0))
            # compute offset from UTC in hours
            tz_off = (datetime.utcoffset(local_time).days * 86400 +
                      datetime.utcoffset(local_time).seconds) / 3600.0

            # What is the jd at 00:00 local time today?
            jd = self.jd_start - (tz_off / 24.0) + d - 1

            self.jd_sunrise[d + 1] = swe.rise_trans(
                jd_start=jd + 1, body=swe.SUN,
                lon=self.city.longitude, lat=self.city.latitude,
                rsmi=swe.CALC_RISE | swe.BIT_DISC_CENTER)[1][0]
            self.jd_sunset[d + 1] = swe.rise_trans(
                jd_start=self.jd_sunrise[d + 1], body=swe.SUN,
                lon=self.city.longitude, lat=self.city.latitude,
                rsmi=swe.CALC_SET | swe.BIT_DISC_CENTER)[1][0]
            self.jd_moonrise[d + 1] = swe.rise_trans(
                jd_start=jd + 1,
                body=swe.MOON, lon=self.city.longitude,
                lat=self.city.latitude,
                rsmi=swe.CALC_RISE | swe.BIT_DISC_CENTER)[1][0]
            self.jd_moonset[d + 1] = swe.rise_trans(
                jd_start=jd + 1, body=swe.MOON,
                lon=self.city.longitude, lat=self.city.latitude,
                rsmi=swe.CALC_SET | swe.BIT_DISC_CENTER)[1][0]

            longitude_sun_sunrise = swe.calc_ut(
                self.jd_sunrise[d + 1], swe.SUN)[0] - swe.get_ayanamsa(self.jd_sunrise[d + 1])
            longitude_sun_sunset = swe.calc_ut(
                self.jd_sunset[d + 1], swe.SUN)[0] - swe.get_ayanamsa(self.jd_sunset[d + 1])

            self.solar_month[d + 1] = int(1 + floor((longitude_sun_sunset % 360) / 30.0))

            solar_month_sunrise[d + 1] = int(1 + floor(((longitude_sun_sunrise) % 360) / 30.0))

            if(d <= 0):
                continue
                # This is just to initialise, since for a lot of calculations,
                # we require comparing with tomorrow's data. This computes the
                # data for day 0, -1.

            # Solar month calculations
            solar_month_end_time = ''
            if month_start_after_sunset is True:
                solar_month_day = 0
                month_start_after_sunset = False

            if self.solar_month[d] != self.solar_month[d + 1]:
                solar_month_day = solar_month_day + 1
                if self.solar_month[d] != solar_month_sunrise[d + 1]:
                    month_start_after_sunset = True
                    [_m, solar_month_end_jd] = get_angam_data(
                        self.jd_sunrise[d], self.jd_sunrise[d + 1], SOLAR_MONTH)[0]
            elif solar_month_sunrise[d] != self.solar_month[d]:
                # sankrAnti!
                # sun moves into next rAshi before sunset
                solar_month_day = 1
                [_m, solar_month_end_jd] = get_angam_data(
                    self.jd_sunrise[d], self.jd_sunrise[d + 1], SOLAR_MONTH)[0]
            else:
                solar_month_day = solar_month_day + 1
                solar_month_end_jd = None

            # if self.solar_month[d-1] != self.solar_month[d]:
            #     # We have a sUrya sankrAnti between yest. and today's sunsets
            #     solar_month_day = 1
            #     if solar_month_sunrise[d] == self.solar_month[d]:
            #         #the sankrAnti happened before today's sunrise
            #         #so search for the end time between yesterday and
            #         #today's sunrises
            #         [_m, solar_month_end_jd] = get_angam_data(self.jd_sunrise[d-1],
            #             self.jd_sunrise[d],SOLAR_MONTH)[0]
            #     else:
            #         #the sankrAnti happens after today's sunrise
            #         #so search for the end time between today and
            #         #tomorrow's sunrises
            #         [_m, solar_month_end_jd] = get_angam_data(self.jd_sunrise[d],
            #             self.jd_sunrise[d + 1],SOLAR_MONTH)[0]
            #     #print ('-----',revjul(jd = solar_month_end_jd, tz_off = tz_off))
            # else:
            #     solar_month_day += 1
            #     solar_month_end_jd = None

            if solar_month_end_jd is None:
                solar_month_end_time = ''
            else:
                solar_month_end_time = '\\mbox{%s {\\tiny \\RIGHTarrow} \\textsf{%s}}' % (
                    NAMES['MASA'][self.script][_m], time(
                        24 * (solar_month_end_jd - jd)).toString(format=self.fmt))

            self.month_data[d] = '\\sunmonth{%s}{%d}{%s}' % (
                NAMES['MASA'][self.script][self.solar_month[d]],
                solar_month_day, solar_month_end_time)
            self.solar_month_day[d] = solar_month_day

            # KARADAYAN NOMBU -- easy to check here
            if solar_month_end_jd is not None:  # month ends today
                if (self.solar_month[d] == 12 and solar_month_day == 1) or\
                   (self.solar_month[d] == 11 and solar_month_day != 1):
                    self.fest_days['ta:kAraDaiyAn2 nOmbu'] = [d]

            # Compute the various kalas
            # Sunrise/sunset and related stuff (like rahu, yama)
            YAMAGANDA_OCTETS = [4, 3, 2, 1, 0, 6, 5]
            RAHUKALA_OCTETS = [7, 1, 6, 4, 5, 3, 2]
            GULIKAKALA_OCTETS = [6, 5, 4, 3, 2, 1, 0]

            self.kalams[d] = {
                'prAtaH sandhyA': get_kalas(self.jd_sunset[d-1], self.jd_sunrise[d], 14, 15),
                'prAtah'        : get_kalas(self.jd_sunrise[d],  self.jd_sunset[d],   0,  5),
                'saGgava'       : get_kalas(self.jd_sunrise[d],  self.jd_sunset[d],   1,  5),
                'madhyAhna'     : get_kalas(self.jd_sunrise[d],  self.jd_sunset[d],   2,  5),
                'aparAhna'      : get_kalas(self.jd_sunrise[d],  self.jd_sunset[d],   3,  5),
                'sAyAhna'       : get_kalas(self.jd_sunrise[d],  self.jd_sunset[d],   4,  5),
                'sAyaM sandhyA' : get_kalas(self.jd_sunrise[d],  self.jd_sunset[d],  14, 15),
                'rahu'          : get_kalas(self.jd_sunrise[d],  self.jd_sunset[d], RAHUKALA_OCTETS[self.weekday[d]]  , 8),
                'yama'          : get_kalas(self.jd_sunrise[d],  self.jd_sunset[d], YAMAGANDA_OCTETS[self.weekday[d]] , 8),
                'gulika'        : get_kalas(self.jd_sunrise[d],  self.jd_sunset[d], GULIKAKALA_OCTETS[self.weekday[d]], 8)
                }

            # Compute all the anga datas
            self.tithi_data[d] = get_angam_data(self.jd_sunrise[d], self.jd_sunrise[d + 1], TITHI)
            self.tithi_sunrise[d] = self.tithi_data[d][0][0]
            self.nakshatram_data[d] = get_angam_data(self.jd_sunrise[d],
                                                     self.jd_sunrise[d + 1], NAKSHATRAM)
            self.nakshatram_sunrise[d] = self.nakshatram_data[d][0][0]
            self.yogam_data[d] = get_angam_data(self.jd_sunrise[d], self.jd_sunrise[d + 1], YOGAM)
            self.karanam_data[d] = get_angam_data(self.jd_sunrise[d],
                                                  self.jd_sunrise[d + 1], KARANAM)
            self.rashi_data[d] = get_angam_data(self.jd_sunrise[d], self.jd_sunrise[d + 1], RASHI)
            if computeLagnams:
                self.lagna_data[d] = get_lagna_data(self.jd_sunrise[d], self.city.latitude,
                                                    self.city.longitude, tz_off)

    def assignLunarMonths(self):
        last_month_change = 1
        last_lunar_month = None
        for d in range(1, MAX_SZ - 1):
            # Assign lunar_month for each day
            if self.tithi_sunrise[d] == 1:
                for i in range(last_month_change, d):
                    if (self.solar_month[d] == last_lunar_month):
                        self.lunar_month[i] = self.solar_month[d] % 12 + 0.5
                    else:
                        self.lunar_month[i] = self.solar_month[d]
                last_month_change = d
                last_lunar_month = self.solar_month[d]
            elif self.tithi_sunrise[d] == 2 and self.tithi_sunrise[d - 1] == 30:
                # prathama tithi was never seen @ sunrise
                for i in range(last_month_change, d):
                    if (self.solar_month[d - 1] == last_lunar_month):
                        self.lunar_month[i] = self.solar_month[d - 1] % 12 + 0.5
                    else:
                        self.lunar_month[i] = self.solar_month[d - 1]
                last_month_change = d
                last_lunar_month = self.solar_month[d - 1]

        for i in range(last_month_change, MAX_SZ - 1):
            self.lunar_month[i] = self.solar_month[last_month_change - 1] + 1

    def get_angams_for_kalas(self, d, get_angam_func, kala_type):
        jd_sunrise = self.jd_sunrise[d]
        jd_sunrise_tmrw = self.jd_sunrise[d + 1]
        jd_sunrise_datmrw = self.jd_sunrise[d + 2]
        jd_sunset = self.jd_sunset[d]
        jd_sunset_tmrw = self.jd_sunset[d + 1]
        jd_moonrise = self.jd_moonrise[d]
        jd_moonrise_tmrw = self.jd_moonrise[d + 1]
        if kala_type == 'sunrise':
            angams = [get_angam_func(jd_sunrise), get_angam_func(jd_sunrise),
                      get_angam_func(jd_sunrise_tmrw), get_angam_func(jd_sunrise_tmrw)]
        elif kala_type == 'sunset':
            angams = [get_angam_func(jd_sunset), get_angam_func(jd_sunset),
                      get_angam_func(jd_sunset_tmrw), get_angam_func(jd_sunset_tmrw)]
        elif kala_type == 'pratah':
            angams = [get_angam_func(jd_sunrise),  # pratah1 start
                      # pratah1 end
                      get_angam_func(jd_sunrise + (jd_sunset - jd_sunrise) * (1.0 / 5.0)),
                      get_angam_func(jd_sunrise_tmrw),  # pratah2 start
                      # pratah2 end
                      get_angam_func(jd_sunrise_tmrw +\
                                     (jd_sunset_tmrw - jd_sunrise_tmrw) * (1.0 / 5.0))]
        elif kala_type == 'sangava':
            angams = [get_angam_func(jd_sunrise + (jd_sunset - jd_sunrise) * (1.0 / 5.0)),
                      get_angam_func(jd_sunrise + (jd_sunset - jd_sunrise) * (2.0 / 5.0)),
                      get_angam_func(jd_sunrise_tmrw +
                                     (jd_sunset_tmrw - jd_sunrise_tmrw) * (1.0 / 5.0)),
                      get_angam_func(jd_sunrise_tmrw +
                                     (jd_sunset_tmrw - jd_sunrise_tmrw) * (2.0 / 5.0))]
        elif kala_type == 'madhyahna':
            angams = [get_angam_func(jd_sunrise + (jd_sunset - jd_sunrise) * (2.0 / 5.0)),
                      get_angam_func(jd_sunrise + (jd_sunset - jd_sunrise) * (3.0 / 5.0)),
                      get_angam_func(jd_sunrise_tmrw +
                                     (jd_sunset_tmrw - jd_sunrise_tmrw) * (2.0 / 5.0)),
                      get_angam_func(jd_sunrise_tmrw + (jd_sunset_tmrw -
                                                        jd_sunrise_tmrw) * (3.0 / 5.0))]
        elif kala_type == 'aparahna':
            angams = [get_angam_func(jd_sunrise + (jd_sunset - jd_sunrise) * (3.0 / 5.0)),
                      get_angam_func(jd_sunrise + (jd_sunset - jd_sunrise) * (4.0 / 5.0)),
                      get_angam_func(jd_sunrise_tmrw +
                                     (jd_sunset_tmrw - jd_sunrise_tmrw) * (3.0 / 5.0)),
                      get_angam_func(jd_sunrise_tmrw +
                                     (jd_sunset_tmrw - jd_sunrise_tmrw) * (4.0 / 5.0))]
        elif kala_type == 'sayahna':
            angams = [get_angam_func(jd_sunrise + (jd_sunset - jd_sunrise) * (4.0 / 5.0)),
                      get_angam_func(jd_sunrise + (jd_sunset - jd_sunrise) * (5.0 / 5.0)),
                      get_angam_func(jd_sunrise_tmrw +
                                     (jd_sunset_tmrw - jd_sunrise_tmrw) * (4.0 / 5.0)),
                      get_angam_func(jd_sunrise_tmrw +
                                     (jd_sunset_tmrw - jd_sunrise_tmrw) * (5.0 / 5.0))]
        elif kala_type == 'madhyaratri':
            angams = [get_angam_func(jd_sunset + (jd_sunrise_tmrw - jd_sunset) * (2.0 / 5.0)),
                      get_angam_func(jd_sunset + (jd_sunrise_tmrw - jd_sunset) * (3.0 / 5.0)),
                      get_angam_func(jd_sunset_tmrw +
                                     (jd_sunrise_datmrw - jd_sunset_tmrw) * (2.0 / 5.0)),
                      get_angam_func(jd_sunset_tmrw +
                                     (jd_sunrise_datmrw - jd_sunset_tmrw) * (3.0 / 5.0))]
        elif kala_type == 'pradosha':
            angams = [get_angam_func(jd_sunset),
                      get_angam_func(jd_sunset + (jd_sunrise_tmrw - jd_sunset) * (1.0 / 5.0)),
                      get_angam_func(jd_sunset_tmrw),
                      get_angam_func(jd_sunset_tmrw +
                                     (jd_sunrise_datmrw - jd_sunset_tmrw) * (1.0 / 5.0))]
        elif kala_type == 'nishita':
            angams = [get_angam_func(jd_sunset + (jd_sunrise_tmrw - jd_sunset) * (7.0 / 15.0)),
                      get_angam_func(jd_sunset + (jd_sunrise_tmrw - jd_sunset) * (8.0 / 15.0)),
                      get_angam_func(jd_sunset_tmrw +
                                     (jd_sunrise_datmrw - jd_sunset_tmrw) * (7.0 / 15.0)),
                      get_angam_func(jd_sunset_tmrw +
                                     (jd_sunrise_datmrw - jd_sunset_tmrw) * (8.0 / 15.0))]
        elif kala_type == 'moonrise':
            angams = [get_angam_func(jd_moonrise), get_angam_func(jd_moonrise),
                      get_angam_func(jd_moonrise_tmrw), get_angam_func(jd_moonrise_tmrw)]
        else:
            # Error!
            raise(ValueError, 'Unkown kala "%s" input!' % kala_type)
            return None
        return angams

    def addFestival(self, festival_name, d, debug=False):
        if debug:
            print('%', d, ':', festival_name, d)
        if festival_name in self.fest_days:
            if d not in self.fest_days[festival_name]:
                # Second occurrence of a festival within a
                # Gregorian calendar year
                self.fest_days[festival_name].append(d)
        else:
            self.fest_days[festival_name] = [d]

    def computeFestivals(self):
        for d in range(1, MAX_DAYS + 1):
            [y, m, dt, t] = swe.revjul(self.jd_start + d - 1)

            # checking @ 6am local - can we do any better?
            local_time = tz(self.city.timezone).localize(datetime(y, m, dt, 6, 0, 0))
            # compute offset from UTC in hours
            tz_off = (datetime.utcoffset(local_time).days * 86400 +
                      datetime.utcoffset(local_time).seconds) / 3600.0

            # What is the jd at 00:00 local time today?
            # jd = self.jd_start - (tz_off / 24.0) + d - 1

            ####################
            # Festival details #
            ####################

            # --- MONTHLY VRATAMS --- #

            # EKADASHI Vratam
            # One of two consecutive tithis must appear @ sunrise!
            if self.tithi_sunrise[d] == 11 or self.tithi_sunrise[d] == 12:
                # check for shukla ekadashi
                if (self.tithi_sunrise[d] == 11 and self.tithi_sunrise[d + 1] == 11):
                    self.festivals[d + 1].append(
                        'sarva~' + get_ekadashi_name('shukla', self.lunar_month[d]))
                    if self.solar_month[d] == 9:
                        self.festivals[d + 1].append('sarva~vaikuNTha~EkAdazI')
                    elif self.solar_month[d] == 8:
                        self.festivals[d + 1].append('sarva~guruvAyupura~EkAdazI')

                elif (self.tithi_sunrise[d] == 11 and self.tithi_sunrise[d + 1] != 11):
                    # Check dashami end time to decide for whether this is
                    # sarva/smartha
                    # Two muhurtams is 1/15 of day-length
                    tithi_arunodayam = get_tithi(
                        self.jd_sunrise[d] - (1 / 15.0) *
                        (self.jd_sunrise[d] - self.jd_sunrise[d - 1]))
                    if tithi_arunodayam == 10:
                        self.festivals[d].append(
                            'smArta~' + get_ekadashi_name('shukla', self.lunar_month[d]))
                        if self.solar_month[d] == 9:
                            self.festivals[d].append('smArta~vaikuNTha~EkAdazI')
                        elif self.solar_month[d] == 8:
                            self.festivals[d].append('smArta~guruvAyupura~EkAdazI')
                        self.festivals[d + 1].append(
                            'vaiSNava~' + get_ekadashi_name('shukla', self.lunar_month[d]))
                        if self.solar_month[d] == 9:
                            self.festivals[d].append('vaiSNava~vaikuNTha~EkAdazI')
                        elif self.solar_month[d] == 8:
                            self.festivals[d].append('vaiSNava~guruvAyupura~EkAdazI')
                    else:
                        self.festivals[d].append(
                            'sarva~' + get_ekadashi_name('shukla', self.lunar_month[d]))
                        if self.solar_month[d] == 9:
                            self.festivals[d].append('sarva~vaikuNTha~EkAdazI')
                        elif self.solar_month[d] == 8:
                            self.festivals[d].append('sarva~guruvAyupura~EkAdazI')

                elif (self.tithi_sunrise[d - 1] != 11 and self.tithi_sunrise[d] == 12):
                    self.festivals[d].append(
                        'sarva~' + get_ekadashi_name('shukla', self.lunar_month[d]))
                    if self.solar_month[d] == 9:
                        self.festivals[d].append('sarva~vaikuNTha~EkAdazI')
                    elif self.solar_month[d] == 8:
                        self.festivals[d].append('sarva~guruvAyupura~EkAdazI')

                # Harivasara Computation
                harivasara_end = brentq(get_angam_float, self.jd_sunrise[d - 2],
                                        self.jd_sunrise[d - 2] + 4, args=(TITHI_PADA, -45, False))
                [_y, _m, _d, _t] = swe.revjul(harivasara_end + (tz_off / 24.0))
                hariv_end_time = time(swe.revjul(harivasara_end + (tz_off / 24.0))[3]).toString()

                fday = swe.julday(_y, _m, _d, 0) - self.jd_start + 1
                self.festivals[int(fday)].append(
                    'harivAsaraH~\\textsf{%s}{\\RIGHTarrow}\\textsf{%s}' % ('', hariv_end_time))

            # One of two consecutive tithis must appear @ sunrise!
            if self.tithi_sunrise[d] == 26 or self.tithi_sunrise[d] == 27:
                # check for krishna ekadashi
                if (self.tithi_sunrise[d] == 26 and self.tithi_sunrise[d + 1] == 26):
                    self.festivals[d + 1].append(
                        'sarva~' + get_ekadashi_name('krishna', self.lunar_month[d]))
                elif (self.tithi_sunrise[d] == 26 and self.tithi_sunrise[d + 1] != 26):
                    # Check dashami end time to decide for whether this is
                    # sarva/smartha
                    # Two muhurtams is 1/15 of day-length
                    tithi_arunodayam = get_tithi(
                        self.jd_sunrise[d] - (1 / 15.0) *
                        (self.jd_sunrise[d] - self.jd_sunrise[d - 1]))
                    if tithi_arunodayam == 25:
                        self.festivals[d].append(
                            'smArta~' + get_ekadashi_name('krishna', self.lunar_month[d]))
                        self.festivals[d + 1].append(
                            'vaiSNava~' + get_ekadashi_name('krishna', self.lunar_month[d]))
                    else:
                        self.festivals[d].append(
                            'sarva~' + get_ekadashi_name('krishna', self.lunar_month[d]))
                elif (self.tithi_sunrise[d - 1] != 26 and self.tithi_sunrise[d] == 27):
                    self.festivals[d].append(
                        'sarva~' + get_ekadashi_name('krishna', self.lunar_month[d]))

                harivasara_end = brentq(get_angam_float, self.jd_sunrise[d - 2],
                                        self.jd_sunrise[d - 2] + 4, args=(TITHI_PADA, -105, False))
                [_y, _m, _d, _t] = swe.revjul(harivasara_end + (tz_off / 24.0))
                hariv_end_time = time(swe.revjul(harivasara_end + (tz_off / 24.0))[3]).toString()

                fday = swe.julday(_y, _m, _d, 0) - self.jd_start + 1
                self.festivals[int(fday)].append(
                    'harivAsaraH~\\textsf{%s}{\\RIGHTarrow}\\textsf{%s}' % ('', hariv_end_time))

            # PRADOSHA Vratam
            pref = ''
            if self.tithi_sunrise[d] == 12 or self.tithi_sunrise[d] == 13:
                tithi_sunset = get_tithi(self.jd_sunset[d])
                tithi_sunset_tmrw = get_tithi(self.jd_sunset[d + 1])
                if tithi_sunset <= 13 and tithi_sunset_tmrw != 13:
                    if self.weekday[d] == 1:
                        pref = 'sOma~'
                    elif self.weekday[d] == 6:
                        pref = 'zani~'
                    self.festivals[d].append(pref + 'pradOSa~vratam')
                elif tithi_sunset_tmrw == 13:
                    if self.weekday[d + 1] == 1:
                        pref = 'sOma~'
                    elif self.weekday[d + 1] == 6:
                        pref = 'zani~'
                    self.festivals[d + 1].append(pref + 'pradOSa~vratam')

            if self.tithi_sunrise[d] == 27 or self.tithi_sunrise[d] == 28:
                tithi_sunset = get_tithi(self.jd_sunset[d])
                tithi_sunset_tmrw = get_tithi(self.jd_sunset[d + 1])
                if tithi_sunset <= 28 and tithi_sunset_tmrw != 28:
                    if self.weekday[d] == 1:
                        pref = 'sOma~'
                    elif self.weekday[d] == 6:
                        pref = 'zani~'
                    self.festivals[d].append(pref + 'pradOSa~vratam')
                elif tithi_sunset_tmrw == 28:
                    if self.weekday[d + 1] == 1:
                        pref = 'sOma~'
                    elif self.weekday[d + 1] == 6:
                        pref = 'zani~'
                    self.festivals[d + 1].append(pref + 'pradOSa~vratam')

            # SANKATAHARA chaturthi
            if self.tithi_sunrise[d] == 18 or self.tithi_sunrise[d] == 19:
                ldiff_moonrise_yest = (swe.calc_ut(self.jd_moonrise[d - 1], swe.MOON)[0] -
                                       swe.calc_ut(self.jd_moonrise[d - 1], swe.SUN)[0]) % 360
                ldiff_moonrise = (swe.calc_ut(self.jd_moonrise[d], swe.MOON)[0] -
                                  swe.calc_ut(self.jd_moonrise[d], swe.SUN)[0]) % 360
                ldiff_moonrise_tmrw = (swe.calc_ut(self.jd_moonrise[d + 1], swe.MOON)[0] -
                                       swe.calc_ut(self.jd_moonrise[d + 1], swe.SUN)[0]) % 360
                tithi_moonrise_yest = int(1 + floor(ldiff_moonrise_yest / 12.0))
                tithi_moonrise = int(1 + floor(ldiff_moonrise / 12.0))
                tithi_moonrise_tmrw = int(1 + floor(ldiff_moonrise_tmrw / 12.0))

                if tithi_moonrise == 19:
                    # otherwise yesterday would have already been assigned
                    if tithi_moonrise_yest != 19:
                        self.festivals[d].append('saGkaTahara-caturthI~vratam')
                        # shravana krishna chaturthi
                        if self.lunar_month[d] == 5:
                            self.festivals[d][-1] = 'mahA' + self.festivals[d][-1]
                elif tithi_moonrise_tmrw == 19:
                    self.festivals[d + 1].append('saGkaTahara-caturthI~vratam')
                    # self.lunar_month[d] and[d + 1] are same, so checking [d] is enough
                    if self.lunar_month[d] == 5:
                        self.festivals[d + 1][-1] = 'mahA' + self.festivals[d + 1][-1]
                else:
                    if tithi_moonrise_yest != 19:
                        if tithi_moonrise == 18 and tithi_moonrise_tmrw == 20:
                            self.festivals[d].append('saGkaTahara-caturthI~vratam')
                            # shravana krishna chaturthi
                            if self.lunar_month[d] == 5:
                                self.festivals[d][-1] = 'mahA' + self.festivals[d][-1]

            # SHASHTHI Vratam
            if self.tithi_sunrise[d] == 5 or self.tithi_sunrise[d] == 6:
                if self.tithi_sunrise[d] == 6 or\
                   (self.tithi_sunrise[d] == 5 and self.tithi_sunrise[d + 1] == 7):
                    # otherwise yesterday would have already been assigned
                    if self.tithi_sunrise[d - 1] != 6:
                        self.festivals[d].append('SaSThI~vratam')
                        # kArtika shukla shashthi
                        if self.lunar_month[d] == 8:
                            self.festivals[d][-1] = 'skanda' + self.festivals[d][-1]
                        elif self.lunar_month[d] == 4:
                            self.festivals[d][-1] = 'kumAra~' + self.festivals[d][-1]
                        elif self.lunar_month[d] == 6:
                            self.festivals[d][-1] = 'SaSThIdEvI~' + self.festivals[d][-1]
                        elif self.lunar_month[d] == 9:
                            self.festivals[d][-1] = 'subrahmaNya~' + self.festivals[d][-1]
                elif self.tithi_sunrise[d + 1] == 6:
                    self.festivals[d + 1].append('SaSThI~vratam')
                    # self.lunar_month[d] and[d + 1] are same, so checking [d] is enough
                    if self.lunar_month[d] == 8:
                        self.festivals[d + 1][-1] = 'skanda' + self.festivals[d + 1][-1]
                    elif self.lunar_month[d] == 4:
                        self.festivals[d + 1][-1] = 'kumAra~' + self.festivals[d + 1][-1]
                    elif self.lunar_month[d] == 6:
                        self.festivals[d + 1][-1] = 'SaSThIdEvI~' + self.festivals[d + 1][-1]
                    elif self.lunar_month[d] == 9:
                        self.festivals[d + 1][-1] = 'subrahmaNya~' + self.festivals[d + 1][-1]

            # Chandra Darshanam
            if self.tithi_sunrise[d] == 1 or self.tithi_sunrise[d] == 2:
                tithi_sunset = get_tithi(self.jd_sunset[d])
                tithi_sunset_tmrw = get_tithi(self.jd_sunset[d + 1])
                if tithi_sunset <= 2 and tithi_sunset_tmrw != 2:
                    if tithi_sunset == 1:
                        self.festivals[d + 1].append('candra-darzanam')
                    else:
                        self.festivals[d].append('candra-darzanam')
                elif tithi_sunset_tmrw == 2:
                    self.festivals[d + 1].append('candra-darzanam')

            # Amavasya Tarpanam
            if d == 1 or self.tithi_sunrise[d] == 1 or self.tithi_sunrise[d] == 2:
                # Reset (at start) every month, as one of these two tithis must hit sunrise!
                t29_end = None
                t30_end = None
            if self.tithi_sunrise[d] == 29 or self.tithi_sunrise[d] == 30:
                if self.tithi_sunrise[d] == 29:
                    t29, t29_end = get_angam_data(
                        self.jd_sunrise[d], self.jd_sunrise[d + 1], TITHI)[0]
                    t30, t30_end = get_angam_data(
                        self.jd_sunrise[d + 1], self.jd_sunrise[d + 2], TITHI)[0]
                    if t30 != 30:
                        # Only 29 ends tomorrow!
                        t30, t30_end = get_angam_data(
                            self.jd_sunrise[d + 1] + 0.5,
                            self.jd_sunrise[d + 2] + 0.5, TITHI)[0]
                if self.tithi_sunrise[d] == 30:
                    if t29_end is None:
                        # 29 never touched sunrise
                        t30, t30_end = get_angam_data(
                            self.jd_sunrise[d], self.jd_sunrise[d + 1], TITHI)[0]
                        t29, t29_end = get_angam_data(t30_end - 1.5, t30_end - 0.5, TITHI)[0]
                if t29_end is None:
                    # Should never be here!
                    sys.stderr.write('Error! Still not computed t29_end!')

                angams = self.get_angams_for_kalas(d, get_tithi, 'aparahna')
                if angams[0] == 30 or angams[1] == 30:
                    if self.lunar_month[d] == 6:
                        pref = '(%s) mahAlaya ' % (
                            get_chandra_masa(self.lunar_month[d], NAMES, 'hk'))
                    elif self.solar_month[d] == 4:
                        pref = '%s (karkaTaka) ' % (
                            get_chandra_masa(self.lunar_month[d], NAMES, 'hk'))
                    elif self.solar_month[d] == 10:
                        pref = 'mauni (%s/makara) ' % (
                            get_chandra_masa(self.lunar_month[d], NAMES, 'hk'))
                    else:
                        pref = get_chandra_masa(self.lunar_month[d], NAMES, 'hk') + '~'
                    if angams[2] == 30 or angams[3] == 30:
                        # Amavasya is there on both aparahnas
                        if t30_end - t29_end < 1:
                            # But not longer than 60 ghatikas
                            self.festivals[d].append(pref + 'amAvasyA')
                        else:
                            # And longer than 60 ghatikas
                            self.festivals[d + 1].append(pref + 'amAvasyA')
                    else:
                        # No Amavasya in aparahna tomorrow, so it's today
                        self.festivals[d].append(pref + 'amAvasyA')

            # MAKARAYANAM
            if self.solar_month[d] == 9 and self.solar_month_day[d] == 1:
                makara_jd_start = brentq(get_nirayana_sun_lon, self.jd_sunrise[d],
                                         self.jd_sunrise[d] + 15, args=(-270, False))

            if self.solar_month[d] == 9 and 3 < self.solar_month_day[d] < 10:
                if self.jd_sunset[d] < makara_jd_start < self.jd_sunset[d + 1]:
                    self.fest_days['makarAyaNa~puNyakAlam/mitrOtsavam'] = [d + 1]

            # KUCHELA DINAM
            if self.solar_month[d] == 9 and self.solar_month_day[d] <= 7 and self.weekday[d] == 3:
                self.fest_days['kucEla~dinam'] = [d]

            # AGNI NAKSHATRAM
            # Arbitrarily checking after Mesha 10! Agni Nakshatram can't start earlier...
            if self.solar_month[d] == 1 and self.solar_month_day[d] == 10:
                agni_jd_start, dummy = get_angam_span(
                    self.jd_sunrise[d], self.jd_sunrise[d] + 30,
                    {'arc_len': 360.0 / 108.0, 'w_moon': 0, 'w_sun': 1}, 7)
                # sys.stderr.write('Agni Start: %s\n' % revjul(agni_jd_start + (5.5 / 24.0)))
                dummy, agni_jd_end = get_angam_span(
                    agni_jd_start, agni_jd_start + 30,
                    {'arc_len': 360.0 / 108.0, 'w_moon': 0, 'w_sun': 1}, 13)
                # sys.stderr.write('Agni End: %s\n' % revjul(agni_jd_end + (5.5 / 24.0)))

            if self.solar_month[d] == 1 and self.solar_month_day[d] > 10:
                if self.jd_sunset[d] < agni_jd_start < self.jd_sunset[d + 1]:
                    self.fest_days['agninakSatra-ArambhaH'] = [d + 1]
            if self.solar_month[d] == 2 and self.solar_month_day[d] > 10:
                if self.jd_sunset[d] < agni_jd_end < self.jd_sunset[d + 1]:
                    self.fest_days['agninakSatra-samApanam'] = [d + 1]

            # GAJACHHAYA YOGA
            if self.solar_month[d] == 6 and self.solar_month_day[d] == 1:
                moon_magha_jd_start = moon_magha_jd_start = t28_start = None
                moon_magha_jd_end = moon_magha_jd_end = t28_end = None
                moon_hasta_jd_start = moon_hasta_jd_start = t30_start = None
                moon_hasta_jd_end = moon_hasta_jd_end = t30_end = None

                sun_hasta_jd_start, sun_hasta_jd_end = get_angam_span(
                    self.jd_sunrise[d], self.jd_sunrise[d] + 30, SOLAR_NAKSH, 13)

                moon_magha_jd_start, moon_magha_jd_end = get_angam_span(
                    sun_hasta_jd_start - 1, sun_hasta_jd_end + 1, NAKSHATRAM, 10)
                if all([moon_magha_jd_start, moon_magha_jd_end]):
                    t28_start, t28_end = get_angam_span(
                        moon_magha_jd_start - 3, moon_magha_jd_end + 3, TITHI, 28)

                moon_hasta_jd_start, moon_hasta_jd_end = get_angam_span(
                    sun_hasta_jd_start - 1, sun_hasta_jd_end + 1, NAKSHATRAM, 13)
                if all([moon_hasta_jd_start, moon_hasta_jd_end]):
                    t30_start, t30_end = get_angam_span(
                        sun_hasta_jd_start - 1, sun_hasta_jd_end + 1, TITHI, 30)

                gc_28 = gc_30 = False

                if all([sun_hasta_jd_start, moon_magha_jd_start, t28_start]):
                    # We have a GC yoga
                    gc_28_start = max(sun_hasta_jd_start, moon_magha_jd_start, t28_start)
                    gc_28_end = min(sun_hasta_jd_end, moon_magha_jd_end, t28_end)

                    if gc_28_start < gc_28_end:
                        gc_28 = True

                if all([sun_hasta_jd_start, moon_hasta_jd_start, t30_start]):
                    # We have a GC yoga
                    gc_30_start = max(sun_hasta_jd_start, moon_hasta_jd_start, t30_start)
                    gc_30_end = min(sun_hasta_jd_end, moon_hasta_jd_end, t30_end)

                    if gc_30_start < gc_30_end:
                        gc_30 = True

            if self.solar_month[d] == 6 and (gc_28 or gc_30):
                if gc_28:
                    gc_28_start += tz_off / 24.0
                    gc_28_end += tz_off / 24.0
                    # sys.stderr.write('28: (%f, %f)\n' % (gc_28_start, gc_28_end))
                    gc_28_d = 1 + floor(gc_28_start - self.jd_start)
                    t1 = time(swe.revjul(gc_28_start)[3]).toString()

                    if floor(gc_28_end - 0.5) != floor(gc_28_start - 0.5):
                        # -0.5 is for the fact that julday is zero at noon always, not midnight!
                        offset = 24
                    else:
                        offset = 0
                    t2 = time(swe.revjul(gc_28_end)[3] + offset).toString()
                    # sys.stderr.write('gajacchhaya %d\n' % gc_28_d)

                    self.fest_days['gajacchAyA~yOgam' +
                                   '~\\textsf{' + t1 + '}{\\RIGHTarrow}\\textsf{' +
                                   t2 + '}'] = [gc_28_d]
                    gc_28 = False
                if gc_30:
                    gc_30_start += tz_off / 24.0
                    gc_30_end += tz_off / 24.0
                    # sys.stderr.write('30: (%f, %f)\n' % (gc_30_start, gc_30_end))
                    gc_30_d = 1 + floor(gc_30_start - self.jd_start)
                    t1 = time(swe.revjul(gc_30_start)[3]).toString()

                    if floor(gc_30_end - 0.5) != floor(gc_30_start - 0.5):
                        offset = 24
                    else:
                        offset = 0
                    t2 = time(swe.revjul(gc_30_end)[3] + offset).toString()
                    # sys.stderr.write('gajacchhaya %d\n' % gc_30_d)

                    self.fest_days['gajacchAyA~yOgam' +
                                   '~\\textsf{' + t1 + '}{\\RIGHTarrow}\\textsf{' +
                                   t2 + '}'] = [gc_30_d]
                    gc_30 = False

            # AYUSHMAN BAVA SAUMYA
            if self.weekday[d] == 3 and get_angam(self.jd_sunrise[d], YOGAM) == 3:
                if get_angam(self.jd_sunrise[d], KARANAM) in list(range(2, 52, 7)):
                    self.addFestival('AyuSmAn-bava-saumya', d, debugFestivals)

            # debugFestivals = True
            debugFestivals = False

            if get_angam(self.jd_sunrise[d], YOGAM) == 17 and self.solar_month[d] == 9:
                self.addFestival('mahAdhanurvyatIpAtam', d, debugFestivals)

            if get_angam(self.jd_sunrise[d], YOGAM) == 17 and self.solar_month[d] == 6:
                self.addFestival('mahAvyatIpAtam', d, debugFestivals)

            # BHANU SAPTAMI
            if self.weekday[d] == 0 and (self.tithi_sunrise[d] % 15) == 7:
                festival_name = 'bhAnusaptamI'
                if self.tithi_sunrise[d] == 7:
                    festival_name = 'vijayA' + '~' + festival_name
                if self.nakshatram_sunrise[d] == 27:
                    # Even more auspicious!
                    festival_name += '*'
                self.addFestival(festival_name, d, debugFestivals)

            # SOMAMAVASYA
            if self.weekday[d] == 1 and self.tithi_sunrise[d] == 30:
                self.addFestival('sOma~amAvasyA', d, debugFestivals)

            # MAHODAYAM
            if self.lunar_month[d] == 10 and self.tithi_sunrise[d] == 30:
                if get_angam(self.jd_sunrise[d], YOGAM) == 17 and\
                   get_angam(self.jd_sunrise[d], NAKSHATRAM) == 22:
                    if self.weekday[d] == 1:
                        festival_name = 'mahodaya~puNyakAlam'
                        self.addFestival(festival_name, d, debugFestivals)
                    elif self.weekday[d] == 0:
                        festival_name = 'ardhodaya~puNyakAlam'
                        self.addFestival(festival_name, d, debugFestivals)

            # MANGALA-CHATURTHI
            if self.weekday[d] == 2 and (self.tithi_sunrise[d] % 15) == 4:
                festival_name = 'aGgAraka~caturthI'
                if self.tithi_sunrise[d] == 4:
                    festival_name = 'sukhA' + '~' + festival_name
                self.addFestival(festival_name, d, debugFestivals)

            # BUDHASHTAMI
            if self.weekday[d] == 3 and (self.tithi_sunrise[d] % 15) == 8:
                self.addFestival('budhASTamI', d, debugFestivals)
                festival_name = 'budhASTamI'

            # AVANI NYAYITRUKIZHAMAI
            if self.solar_month[d] == 5 and self.weekday[d] == 0:
                self.addFestival('ta:AvaNi~JAyir2r2ukkizhamai', d, debugFestivals)

            # PURATTASI SANIKKIZHAMAI
            if self.solar_month[d] == 6 and self.weekday[d] == 6:
                self.addFestival('ta:puraTTAci can2ikkizhamai', d, debugFestivals)

            # KARTHIKAI NYAYITRUKIZHAMAI
            if self.solar_month[d] == 8 and self.weekday[d] == 0:
                self.addFestival('ta:kArttigai~JAyir2r2ukkizhamai', d, debugFestivals)

            # KRTTIKA SOMAVASARA
            if self.solar_month[d] == 8 and self.weekday[d] == 1:
                self.addFestival('ta:kArttigai~sOmavAram', d, debugFestivals)

            # AADI VELLI
            if self.solar_month[d] == 4 and self.weekday[d] == 5:
                self.addFestival('ta:ADi~veLLikkizhamai', d, debugFestivals)

            # TAI
            if self.solar_month[d] == 10 and self.weekday[d] == 5:
                self.addFestival('ta:tai~veLLikkizhamai', d, debugFestivals)

            # MASI SEVVAI
            if self.solar_month[d] == 11 and self.weekday[d] == 2:
                self.addFestival('ta:mAci~cevvAy', d, debugFestivals)

            # BHAUMASHWINI
            if (self.nakshatram_sunrise[d] == 27 or self.nakshatram_sunrise[d] == 1)\
               and self.weekday[d] == 2:
                # Is it necessarily only at sunrise?
                # angams = self.get_angams_for_kalas(d, get_nakshatram, 'madhyahna')
                # if any(x == 1 for x in [self.nakshatram_sunrise[d], angams[0], angams[1]]):
                if any(x == 1 for x in [self.nakshatram_sunrise[d]]):
                    self.addFestival('bhaumAzvinI~puNyakAlam', d, debugFestivals)

            # BUDHANURADHA
            if (self.nakshatram_sunrise[d] == 16 or self.nakshatram_sunrise[d] == 17)\
               and self.weekday[d] == 3:
                # Is it necessarily only at sunrise?
                # angams = self.get_angams_for_kalas(d, get_nakshatram, 'madhyahna')
                # if any(x == 17 for x in [self.nakshatram_sunrise[d], angams[0], angams[1]]):
                if any(x == 17 for x in [self.nakshatram_sunrise[d]]):
                    self.addFestival('budhAnUrAdhA~puNyakAlam', d, debugFestivals)

            with open('festival_rules.json') as festivals_data:
                festival_rules = json.load(festivals_data)

            for festival_name in festival_rules:
                if 'Month Type' in festival_rules[festival_name]:
                    month_type = festival_rules[festival_name]['Month Type']
                else:
                    # Maybe only description of the festival is given, as computation has been
                    # done in computeFestivals(), without using a rule in festival_rules.json!
                    if 'Short Description' in festival_rules[festival_name]:
                        continue
                    raise(ValueError, "No month_type mentioned for %s" % festival_name)
                if 'Month Number' in festival_rules[festival_name]:
                    month_num = festival_rules[festival_name]['Month Number']
                else:
                    raise(ValueError, "No month_num mentioned for %s" % festival_name)
                if 'Angam Type' in festival_rules[festival_name]:
                    angam_type = festival_rules[festival_name]['Angam Type']
                else:
                    raise(ValueError, "No angam_type mentioned for %s" % festival_name)
                if 'Angam Number' in festival_rules[festival_name]:
                    angam_num = festival_rules[festival_name]['Angam Number']
                else:
                    raise(ValueError, "No angam_num mentioned for %s" % festival_name)
                if 'kala' in festival_rules[festival_name]:
                    kala = festival_rules[festival_name]['kala']
                else:
                    kala = 'sunrise'
                if 'priority' in festival_rules[festival_name]:
                    priority = festival_rules[festival_name]['priority']
                else:
                    priority = 'purvaviddha'
                if 'Start Year' in festival_rules[festival_name]:
                    fest_start_year = festival_rules[festival_name]['Start Year']
                else:
                    fest_start_year = None
                # if 'Other Names' in festival_rules[festival_name]:
                #     fest_other_names = festival_rules[festival_name]['Other Names']
                # if 'Nirnaya' in festival_rules[festival_name]:
                #     fest_nirnaya = festival_rules[festival_name]['Nirnaya']
                # if 'Primary Reference' in festival_rules[festival_name]:
                #     fest_ref1 = festival_rules[festival_name]['Primary Reference']
                # if 'Secondary Reference' in festival_rules[festival_name]:
                #     fest_ref2 = festival_rules[festival_name]['Secondary Reference']
                # if 'Comments' in festival_rules[festival_name]:
                #     fest_comments = festival_rules[festival_name]['Comments']

                if angam_type == 'tithi' and month_type == 'lunar_month' and\
                   angam_num == 1:
                    # Shukla prathama tithis need to be dealt carefully, if e.g. the prathama tithi
                    # does not touch sunrise on either day (the regular check won't work, because
                    # the month itself is different the previous day!)
                    if self.tithi_sunrise[d] == 30 and self.tithi_sunrise[d + 1] == 2 and\
                       self.lunar_month[d + 1] == month_num:
                        # Only in this case, we have a problem
                        fest_num = None
                        if fest_start_year is not None:
                            if month_type == 'lunar_month':
                                fest_num = self.year + 3100 +\
                                    (d >= self.lunar_month.index(1)) - fest_start_year + 1

                        if fest_num is not None and fest_num < 0:
                            print('Festival %s is only in the future!' % festival_name)
                            return

                        if fest_num is not None:
                            festival_name += '~\\#{%d}' % fest_num

                        self.addFestival(festival_name, d, debugFestivals)
                        continue

                if angam_type == 'day' and month_type == 'solar_month'\
                   and self.solar_month[d] == month_num:
                        if self.solar_month_day[d] == angam_num:
                            self.fest_days[festival_name] = [d]
                elif (month_type == 'lunar_month' and self.lunar_month[d] == month_num) or\
                     (month_type == 'solar_month' and self.solar_month[d] == month_num):
                    if angam_type == 'tithi':
                        angam_sunrise = self.tithi_sunrise
                        get_angam_func = get_tithi
                    elif angam_type == 'nakshatram':
                        angam_sunrise = self.nakshatram_sunrise
                        get_angam_func = get_nakshatram
                    else:
                        raise ValueError('Error; unknown string in rule: "%s"' % (angam_type))
                        return

                    fday = None
                    fest_num = None
                    if fest_start_year is not None and month_type is not None:
                        if month_type == 'solar_month':
                            fest_num = self.year + 3100 +\
                                (d >= self.solar_month.index(1)) - fest_start_year + 1
                        elif month_type == 'lunar_month':
                            fest_num = self.year + 3100 +\
                                (d >= self.lunar_month.index(1)) - fest_start_year + 1

                    if fest_num is not None and fest_num < 0:
                        print('Festival %s is only in the future!' % festival_name)
                        return

                    if fest_num is not None:
                        festival_name += '~\\#{%d}' % fest_num

                    if angam_sunrise[d] == angam_num - 1 or angam_sunrise[d] == angam_num:
                        angams = self.get_angams_for_kalas(d, get_angam_func, kala)
                        if angams is None:
                            sys.stderr.write('No angams returned! Skipping festival %s'
                                             % festival_name)
                            continue
                            # Some error, e.g. weird kala, so skip festival
                        if debugFestivals:
                            print('%' * 80)
                            print('%', festival_name, ': ', festival_rules[festival_name])
                            print("%%angams today & tmrw:", angams)
                        if priority == 'paraviddha':
                            if angams[0] == angam_num or angams[1] == angam_num:
                                fday = d
                            if angams[2] == angam_num or angams[3] == angam_num:
                                fday = d + 1
                            if fday is None:
                                if debugFestivals:
                                    print('%', angams, angam_num)
                                sys.stderr.write('Could not assign paraviddha day for %s!' %
                                                 festival_name +
                                                 ' Please check for unusual cases.\n')
                            else:
                                sys.stderr.write('Assigned paraviddha day for %s!' %
                                                 festival_name + ' Ignore future warnings!\n')
                        elif priority == 'purvaviddha':
                            angams_yest = self.get_angams_for_kalas(d - 1, get_angam_func, kala)
                            if debugFestivals:
                                print("%angams yest & today:", angams_yest)
                            if angams[0] == angam_num or angams[1] == angam_num:
                                if festival_name in self.fest_days:
                                    # Check if yesterday was assigned already
                                    # to this purvaviddha festival!
                                    if self.fest_days[festival_name].count(d - 1) == 0:
                                        fday = d
                                else:
                                    fday = d
                            elif angams[2] == angam_num or angams[3] == angam_num:
                                fday = d + 1
                            if fday is None:
                                # This means that the correct angam did not
                                # touch the kalam on either day!
                                # sys.stderr.write('Could not assign purvaviddha day for %s!\
                                # Please check for unusual cases.\n' % festival_name)
                                if angams[2] == angam_num + 1 or angams[3] == angam_num + 1:
                                    # Need to assign a day to the festival here
                                    # since the angam did not touch kalam on either day
                                    # BUT ONLY IF YESTERDAY WASN'T ALREADY ASSIGNED,
                                    # THIS BEING PURVAVIDDHA
                                    # Perhaps just need better checking of
                                    # conditions instead of this fix
                                    if festival_name in self.fest_days:
                                        if self.fest_days[festival_name].count(d - 1) == 0:
                                            fday = d
                                    else:
                                        fday = d
                        else:
                            sys.stderr.write('Unknown priority "%s" for %s! Check the rules!' %
                                             (priority, festival_name))
                    # print (self.fest_days)
                    if fday is not None:
                        self.addFestival(festival_name, fday, debugFestivals)

            # distance from prabhava
            samvatsara_id = (self.year - 1568) % 60 + 1
            new_yr = 'mESa~saGkrAnti' + '~(' + NAMES['YEAR']['hk'][(samvatsara_id % 60) + 1] +\
                     '-' + 'saMvatsaraH' + ')'

            if self.solar_month[d] == 1 and self.solar_month[d - 1] == 12:
                self.fest_days[new_yr] = [d]

        # If tripurotsava coincides with maha kArtikI (kRttikA nakShatram)
        # only then it is mahAkArtikI
        # else it is only tripurotsava
        if self.fest_days['tripurOtsavaH'] != self.fest_days['mahA-kArtikI']:
            del self.fest_days['mahA-kArtikI']
            # An error here implies the festivals were not assigned: adhika
            # mAsa calc errors??

        # Add "RELATIVE" festivals --- festivals that happen before or
        # after other festivals with an exact timedelta!
        self.fest_days['gAyatrI~japam'] = [self.fest_days['yajurvEda-upAkarma'][0] + 1]
        self.fest_days['varalakSmI-vratam'] =\
            [self.fest_days['yajurvEda-upAkarma'][0] -
             ((self.weekday_start - 1 + self.fest_days['yajurvEda-upAkarma'][0] - 5) % 7)]
        self.fest_days['bhOgI'] = [self.fest_days['makara~saGkrAnti/uttarAyaNa-puNyakAlam'][0] - 1]
        self.fest_days['hOli'] = [self.fest_days['hOlikA~pUrNimA'][0] + 1]
        self.fest_days['indra~pUjA/gO~pUjA'] =\
            [self.fest_days['makara~saGkrAnti/uttarAyaNa-puNyakAlam'][0] + 1]
        self.fest_days['ta:kan2up~poGgal'] =\
            [self.fest_days['makara~saGkrAnti/uttarAyaNa-puNyakAlam'][0] + 1]

        # KAPALI FESTIVALS
        panguni_uttaram = self.fest_days['ta:paGgun2i~uttiram'][-1]
        self.fest_days['ta:kapAlI dvajArOhaNam'] = [panguni_uttaram - 9]
        self.fest_days['ta:kapAlI sUrya-candra-vaTTam'] = [panguni_uttaram - 8]
        self.fest_days['ta:kapAlI adhikAra nandi'] = [panguni_uttaram - 7]
        self.fest_days['ta:kapAlI bhUtaN bhUtakI'] = [panguni_uttaram - 7]
        # self.fest_days['ta:kapAlI veLLi bhUta vAhan2am'] = [panguni_uttaram - 6]
        self.fest_days['ta:kapAlI cavuDal vimAn2am'] = [panguni_uttaram - 5]
        self.fest_days['ta:kapAlI riSabha vAhan2am'] = [panguni_uttaram - 5]
        self.fest_days['ta:kapAlI pallakku vizhA'] = [panguni_uttaram - 4]
        self.fest_days['ta:kapAlI tEr'] = [panguni_uttaram - 3]
        self.fest_days['ta:kapAlI ar2upattu mUvar'] = [panguni_uttaram - 2]
        # self.fest_days['ta:kapAlI bhikSATan2ar'] = [panguni_uttaram - 1]
        self.fest_days['ta:kapAlI umA-mahezvara darican2am'] = [panguni_uttaram + 1]
        self.fest_days['ta:kapAlI viDaiyAr2r2i toDakkam'] = [panguni_uttaram + 1]
        self.fest_days['ta:kapAlI viDaiyAr2r2i nir2aivu'] = [panguni_uttaram + 11]

        self.fest_days['ta:kapAlI teppOtsavam'] = [self.fest_days['ta:taippUcam'][-1] - 1,
                                                   self.fest_days['ta:taippUcam'][-1],
                                                   self.fest_days['ta:taippUcam'][-1] + 1]

        # CHIDAMBARAM FESTIVALS
        aani_tirumanjanam = self.fest_days['ta:naTarAjar An2i tirumaJcan2am'][-1]
        self.fest_days['ta:cidambaram dvajArOhaNam/paJcamUrtti bhavan2i'] = [aani_tirumanjanam - 9]
        self.fest_days['ta:cidambaram veLLi candraprabha vAhan2am'] = [aani_tirumanjanam - 8]
        self.fest_days['ta:cidambaram taGga sUryaprabha vAhan2am'] = [aani_tirumanjanam - 7]
        self.fest_days['ta:cidambaram veLLi bhUta vAhan2am'] = [aani_tirumanjanam - 6]
        self.fest_days['ta:cidambaram veLLi riSabha vAhan2am'] = [aani_tirumanjanam - 5]
        self.fest_days['ta:cidambaram veLLi yAn2ai vAhan2am'] = [aani_tirumanjanam - 4]
        self.fest_days['ta:cidambaram kailAca vAhan2am'] = [aani_tirumanjanam - 3]
        self.fest_days['ta:cidambaram bhikSATan2ar taGga ratham'] = [aani_tirumanjanam - 2]
        self.fest_days['ta:cidambaram tEr'] = [aani_tirumanjanam - 1]
        self.fest_days['ta:cidambaram muttuppallakku'] = [aani_tirumanjanam + 1]

        if debugFestivals:
            print('%', self.fest_days)

        for festival_name in self.fest_days:
            for j in range(0, len(self.fest_days[festival_name])):
                self.festivals[self.fest_days[festival_name][j]].append(festival_name)

    def computeSolarEclipses(self):
        # Set location
        swe.set_topo(lon=self.city.longitude, lat=self.city.latitude, alt=0.0)
        jd = self.jd_start
        while 1:
            next_eclipse_sol = swe.sol_eclipse_when_loc(
                julday=jd, lon=self.city.longitude, lat=self.city.latitude)
            [y, m, dt, t] = swe.revjul(next_eclipse_sol[1][0])
            local_time = tz(self.city.timezone).localize(
                datetime(y, m, dt, 6, 0, 0))
            # checking @ 6am local - can we do any better?
            tz_off = (datetime.utcoffset(local_time).days * 86400 +
                      datetime.utcoffset(local_time).seconds) / 3600.0
            # compute offset from UTC
            jd = next_eclipse_sol[1][0] + (tz_off / 24.0)
            jd_eclipse_solar_start = next_eclipse_sol[1][1] + (tz_off / 24.0)
            jd_eclipse_solar_end = next_eclipse_sol[1][4] + (tz_off / 24.0)
            # -1 is to not miss an eclipse that occurs after sunset on 31-Dec!
            eclipse_y = swe.revjul(jd - 1)[0]
            if eclipse_y != self.year:
                break
            else:
                fday = int(floor(jd) - floor(self.jd_start) + 1)
                if (jd < (self.jd_sunrise[fday] + tz_off / 24.0)):
                    fday -= 1
                eclipse_solar_start = swe.revjul(
                    jd_eclipse_solar_start)[3]
                eclipse_solar_end = swe.revjul(jd_eclipse_solar_end)[3]
                if (jd_eclipse_solar_start - (tz_off / 24.0)) == 0.0 or\
                   (jd_eclipse_solar_end - (tz_off / 24.0)) == 0.0:
                    # Move towards the next eclipse... at least the next new
                    # moon (>=25 days away)
                    jd += MIN_DAYS_NEXT_ECL
                    continue
                if eclipse_solar_end < eclipse_solar_start:
                    eclipse_solar_end += 24
                sunrise_eclipse_day = swe.revjul(self.jd_sunrise[fday])[3]
                sunset_eclipse_day = swe.revjul(self.jd_sunset[fday])[3]
                jd_sunrise_eclipse_day = self.jd_sunrise[fday]
                jd_sunset_eclipse_day = self.jd_sunset[fday]
                if jd_eclipse_solar_start < jd_sunrise_eclipse_day:
                    eclipse_solar_start = sunrise_eclipse_day
                if jd_eclipse_solar_end > jd_sunset_eclipse_day:
                    eclipse_solar_end = sunset_eclipse_day
                solar_eclipse_str = 'sUrya-grahaNam' +\
                    '~\\textsf{' + time(eclipse_solar_start).toString() +\
                    '}{\\RIGHTarrow}\\textsf{' + time(eclipse_solar_end).toString() + '}'
                self.festivals[fday].append(solar_eclipse_str)
            jd = jd + MIN_DAYS_NEXT_ECL

    def computeLunarEclipses(self):
        # Set location
        swe.set_topo(lon=self.city.longitude, lat=self.city.latitude, alt=0.0)
        jd = self.jd_start
        while 1:
            next_eclipse_lun = swe.lun_eclipse_when(jd)
            [y, m, dt, t] = swe.revjul(next_eclipse_lun[1][0])
            local_time = tz(self.city.timezone).localize(
                datetime(y, m, dt, 6, 0, 0))
            # checking @ 6am local - can we do any better? This is crucial,
            # since DST changes before 6 am
            tz_off = (datetime.utcoffset(local_time).days * 86400 +
                      datetime.utcoffset(local_time).seconds) / 3600.0
            # compute offset from UTC
            jd = next_eclipse_lun[1][0] + (tz_off / 24.0)
            jd_eclipse_lunar_start = next_eclipse_lun[1][2] + (tz_off / 24.0)
            jd_eclipse_lunar_end = next_eclipse_lun[1][3] + (tz_off / 24.0)
            # -1 is to not miss an eclipse that occurs after sunset on 31-Dec!
            eclipse_y = swe.revjul(jd - 1)[0]
            if eclipse_y != self.year:
                break
            else:
                eclipse_lunar_start = swe.revjul(
                    jd_eclipse_lunar_start)[3]
                eclipse_lunar_end = swe.revjul(jd_eclipse_lunar_end)[3]
                if (jd_eclipse_lunar_start - (tz_off / 24.0)) == 0.0 or\
                   (jd_eclipse_lunar_end - (tz_off / 24.0)) == 0.0:
                    # Move towards the next eclipse... at least the next full
                    # moon (>=25 days away)
                    jd += MIN_DAYS_NEXT_ECL
                    continue
                fday = int(
                    floor(jd_eclipse_lunar_start) - floor(self.jd_start) + 1)
                # print '%%', jd, fday, self.jd_sunrise[fday],
                # self.jd_sunrise[fday-1]
                if (jd < (self.jd_sunrise[fday] + tz_off / 24.0)):
                    fday -= 1
                if eclipse_lunar_start < swe.revjul(self.jd_sunrise[fday + 1] + tz_off / 24.0)[3]:
                    eclipse_lunar_start += 24
                # print '%%', jd, fday, self.jd_sunrise[fday],
                # self.jd_sunrise[fday-1], eclipse_lunar_start,
                # eclipse_lunar_end
                jd_moonrise_eclipse_day = swe.rise_trans(
                    jd_start=self.jd_sunrise[fday], body=swe.MOON, lon=self.city.longitude,
                    lat=self.city.latitude, rsmi=swe.CALC_RISE | swe.BIT_DISC_CENTER)[1][0] +\
                    (tz_off / 24.0)
                jd_moonset_eclipse_day = swe.rise_trans(
                    jd_start=jd_moonrise_eclipse_day, body=swe.MOON, lon=self.city.longitude,
                    lat=self.city.latitude, rsmi=swe.CALC_SET | swe.BIT_DISC_CENTER)[1][0] +\
                    (tz_off / 24.0)

                if eclipse_lunar_end < eclipse_lunar_start:
                    eclipse_lunar_end += 24

                if jd_eclipse_lunar_end < jd_moonrise_eclipse_day or\
                   jd_eclipse_lunar_start > jd_moonset_eclipse_day:
                    # Move towards the next eclipse... at least the next full
                    # moon (>=25 days away)
                    jd += MIN_DAYS_NEXT_ECL
                    continue

                moonrise_eclipse_day = swe.revjul(jd_moonrise_eclipse_day)[3]
                moonset_eclipse_day = swe.revjul(jd_moonset_eclipse_day)[3]

                if jd_eclipse_lunar_start < jd_moonrise_eclipse_day:
                    eclipse_lunar_start = moonrise_eclipse_day
                if jd_eclipse_lunar_end > jd_moonset_eclipse_day:
                    eclipse_lunar_end = moonset_eclipse_day

                lunar_eclipse_str = 'candra-grahaNam' +\
                    '~\\textsf{' + time(eclipse_lunar_start).toString() +\
                    '}{\\RIGHTarrow}\\textsf{' + time(eclipse_lunar_end).toString() + '}'

                self.festivals[fday].append(lunar_eclipse_str)
            jd += MIN_DAYS_NEXT_ECL

    def writeMonthlyTeX(self, template_file):
        """Write out the panchangam TeX using a specified template
        """
        day_colours = {0: 'blue', 1: 'blue', 2: 'blue',
                       3: 'blue', 4: 'blue', 5: 'blue', 6: 'blue'}
        month = {1: 'JANUARY', 2: 'FEBRUARY', 3: 'MARCH', 4: 'APRIL',
                 5: 'MAY', 6: 'JUNE', 7: 'JULY', 8: 'AUGUST', 9: 'SEPTEMBER',
                 10: 'OCTOBER', 11: 'NOVEMBER', 12: 'DECEMBER'}
        MON = {1: 'January', 2: 'February', 3: 'March', 4: 'April',
               5: 'May', 6: 'June', 7: 'July', 8: 'August', 9: 'September',
               10: 'October', 11: 'November', 12: 'December'}
        WDAY = {0: 'Sun', 1: 'Mon', 2: 'Tue',
                3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat'}

        template_lines = template_file.readlines()
        for i in range(0, len(template_lines) - 3):
            print(template_lines[i][:-1])

        samvatsara_id = (self.year - 1568) % 60 + 1  # distance from prabhava
        samvatsara_names = '%s–%s' % (NAMES['YEAR'][self.script][samvatsara_id],
                                      NAMES['YEAR'][self.script][(samvatsara_id % 60) + 1])

        print('\\mbox{}')
        print('{\\font\\x="Candara" at 60 pt\\x %d\\\\[0.5cm]}' % self.year)
        print('\\mbox{\\font\\x="Sanskrit 2003:script=deva" at 48 pt\\x %s}\\\\[0.5cm]' %
              samvatsara_names)
        print('\\mbox{\\font\\x="Sanskrit 2003:script=deva" at 32 pt\\x %s } %%'
              % tr('kali', self.script))
        print('{\\font\\x="Candara" at 32 pt\\x %d–%d\\\\[0.5cm]}'
              % (self.year + 3100, self.year + 3101))
        print('{\\font\\x="Candara" at 48 pt\\x \\uppercase{%s}\\\\[0.2cm]}' %
              self.city.name)
        print('{\\font\\x="Candara" at 16 pt\\x {%s}\\\\[0.5cm]}' %
              print_lat_lon(self.city.latstr, self.city.lonstr))
        print('\hrule')

        print('\\newpage')
        print('\\centering')
        print('\\centerline{\\LARGE {{%s}}}' % tr('mAsAntara-vizESAH', self.script))
        print('\\begin{multicols*}{3}')
        print('\\TrickSupertabularIntoMulticols')
        print('\\begin{supertabular}' +
              '{>{\\sffamily}r>{\\sffamily}r>{\\sffamily}c>{\\hangindent=2ex}p{8cm}}')

        mlast = 1
        for d in range(1, MAX_SZ - 1):
            [y, m, dt, t] = swe.revjul(self.jd_start + d - 1)

            # checking @ 6am local - can we do any better?
            local_time = tz(self.city.timezone).localize(datetime(y, m, dt, 6, 0, 0))
            # compute offset from UTC in hours
            tz_off = (datetime.utcoffset(local_time).days * 86400 +
                      datetime.utcoffset(local_time).seconds) / 3600.0

            # What is the jd at 00:00 local time today?
            jd = self.jd_start - tz_off / 24.0 + d - 1

            if len(self.festivals[d]) != 0:
                if m != mlast:
                    mlast = m
                    print('\\\\')

                print('%s & %s & %s & {\\raggedright %s} \\\\' %
                      (MON[m], dt, WDAY[self.weekday[d]],
                       '\\\\'.join([tr(f, self.script, True, True)
                                    for f in sorted(set(self.festivals[d]))])))

            if m == 12 and dt == 31:
                break

        print('\\end{supertabular}')
        print('\\end{multicols*}')
        print('\\renewcommand{\\tamil}[1]{%')
        print('{\\fontspec{Vijaya}\\fontsize{7}{12}\\selectfont #1}}')

        # print('\\clearpage')

        for d in range(1, MAX_SZ - 1):
            [y, m, dt, t] = swe.revjul(self.jd_start + d - 1)

            # checking @ 6am local - can we do any better?
            local_time = tz(self.city.timezone).localize(datetime(y, m, dt, 6, 0, 0))
            # compute offset from UTC in hours
            tz_off = (datetime.utcoffset(local_time).days * 86400 +
                      datetime.utcoffset(local_time).seconds) / 3600.0

            # What is the jd at 00:00 local time today?
            jd = self.jd_start - (tz_off / 24.0) + d - 1

            if dt == 1:
                if m > 1:
                    if self.weekday[d] != 0:  # Space till Sunday
                        for i in range(self.weekday[d], 6):
                            print("{}  &")
                        print("\\\\ \hline")
                    print('\end{tabular}')
                    print('\n\n')

                # Begin tabular
                print('\\begin{tabular}{|c|c|c|c|c|c|c|}')
                print('\multicolumn{7}{c}{\Large \\bfseries \sffamily %s %s}\\\\[3mm]' % (
                    month[m], y))
                print('\hline')
                WDAY_NAMES = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
                print(' & '.join(['\\textbf{\\textsf{%s}}' %
                                  _day for _day in WDAY_NAMES]) + ' \\\\ \hline')

                # Blanks for previous weekdays
                for i in range(0, self.weekday[d]):
                    print("{}  &")

            tithi_data_str = ''
            for tithi_ID, tithi_end_jd in self.tithi_data[d]:
                # if tithi_data_str != '':
                #     tithi_data_str += '\\hspace{2ex}'
                tithi = '\moon[scale=0.6]{%d}~' % (tithi_ID) +\
                        NAMES['TITHI'][self.script][tithi_ID]
                if tithi_end_jd is None:
                    tithi_data_str = '%s\\mbox{%s {\\tiny \\RIGHTarrow} %s}' %\
                                     (tithi_data_str, tithi, tr('ahOrAtram', self.script))
                else:
                    tithi_data_str = '%s\\mbox{%s {\\tiny \\RIGHTarrow} \\textsf{%s%s}}' %\
                                     (tithi_data_str, tithi,
                                      time(24 * (tithi_end_jd - jd)).toString(format=self.fmt),
                                      '\\hspace{2ex}')

            nakshatram_data_str = ''
            for nakshatram_ID, nakshatram_end_jd in self.nakshatram_data[d]:
                # if nakshatram_data_str != '':
                #     nakshatram_data_str += '\\hspace{2ex}'
                nakshatram = NAMES['NAKSHATRAM'][self.script][nakshatram_ID]
                if nakshatram_end_jd is None:
                    nakshatram_data_str = '%s\\mbox{%s {\\tiny \\RIGHTarrow} %s}' %\
                                          (nakshatram_data_str, nakshatram,
                                           tr('ahOrAtram', self.script))
                else:
                    nakshatram_data_str = '%s\\mbox{%s {\\tiny \\RIGHTarrow} \\textsf{%s%s}}' %\
                                          (nakshatram_data_str, nakshatram,
                                           time(24 * (nakshatram_end_jd -
                                                      jd)).toString(format=self.fmt),
                                           '\\hspace{2ex}')

            yogam_data_str = ''
            for yogam_ID, yogam_end_jd in self.yogam_data[d]:
                # if yogam_data_str != '':
                #     yogam_data_str += '\\hspace{2ex}'
                yogam = NAMES['YOGAM'][self.script][yogam_ID]
                if yogam_end_jd is None:
                    yogam_data_str = '%s\\mbox{%s {\\tiny \\RIGHTarrow} %s}' %\
                                     (yogam_data_str, yogam, tr('ahOrAtram', self.script))
                else:
                    yogam_data_str = '%s\\mbox{%s {\\tiny \\RIGHTarrow} \\textsf{%s%s}}' %\
                                     (yogam_data_str, yogam,
                                      time(24 * (yogam_end_jd - jd)).toString(format=self.fmt),
                                      '\\hspace{2ex}')

            karanam_data_str = ''
            for numKaranam, (karanam_ID, karanam_end_jd) in enumerate(self.karanam_data[d]):
                # if numKaranam == 1:
                #     karanam_data_str += '\\hspace{2ex}'
                if numKaranam == 2:
                    karanam_data_str = karanam_data_str + '\\\\'
                karanam = NAMES['KARANAM'][self.script][karanam_ID]
                if karanam_end_jd is None:
                    karanam_data_str = '%s\\mbox{%s {\\tiny \\RIGHTarrow} %s}' %\
                                       (karanam_data_str, karanam,
                                        tr('ahOrAtram', self.script))
                else:
                    karanam_data_str = '%s\\mbox{%s {\\tiny \\RIGHTarrow} \\textsf{%s%s}}' %\
                                       (karanam_data_str, karanam,
                                        time(24 * (karanam_end_jd -
                                                   jd)).toString(format=self.fmt), '\\hspace{2ex}')

            sunrise = time(24 * (self.jd_sunrise[d] - jd)).toString(format=self.fmt)
            sunset = time(24 * (self.jd_sunset[d] - jd)).toString(format=self.fmt)
            sangava = time(24 * (self.kalams[d]['saGgava'][0] - jd)).toString(format=self.fmt)
            rahu = '%s--%s' % (
                time(24 * (self.kalams[d]['rahu'][0] - jd)).toString(format=self.fmt),
                time(24 * (self.kalams[d]['rahu'][1] - jd)).toString(format=self.fmt))
            yama = '%s--%s' % (
                time(24 * (self.kalams[d]['yama'][0] - jd)).toString(format=self.fmt),
                time(24 * (self.kalams[d]['yama'][1] - jd)).toString(format=self.fmt))

            print('\caldata{\\textcolor{%s}{%s}}{%s{%s}}%%' %
                  (day_colours[self.weekday[d]], dt, self.month_data[d],
                   get_chandra_masa(self.lunar_month[d], NAMES, self.script)))
            print('{\\sundata{%s}{%s}{%s}}%%' % (sunrise, sunset, sangava))
            print('{\\tnyk{%s}%%\n{%s}%%\n{%s}%%\n{%s}}%%' % (tithi_data_str, nakshatram_data_str,
                                                              yogam_data_str, karanam_data_str))
            print('{\\rahuyama{%s}{%s}}%%' % (rahu, yama))

            # Using set as an ugly workaround since we may have sometimes assigned the same
            # festival to the same day again!
            print('{%s}' % '\\eventsep '.join(
                [tr(f, self.script, True, True) for f in sorted(set(self.festivals[d]))]))

            if self.weekday[d] == 6:
                print("\\\\ \hline")
            else:
                print("&")

            if m == 12 and dt == 31:
                break

            # For debugging specific dates
            # if m==4 and dt==10:
            #  break

        for i in range(self.weekday[d] + 1, 6):
            print("{}  &")
        if self.weekday[d] != 6:
            print("\\\\ \hline")
        print('\end{tabular}')
        print('\n\n')

        print(template_lines[-2][:-1])
        print(template_lines[-1][:-1])

    def writeDailyTeX(self, template_file, computeLagnams=True):
        """Write out the panchangam TeX using a specified template
        """
        # day_colours = {0: 'blue', 1: 'blue', 2: 'blue',
        #                3: 'blue', 4: 'blue', 5: 'blue', 6: 'blue'}
        month = {1: 'JANUARY', 2: 'FEBRUARY', 3: 'MARCH', 4: 'APRIL',
                 5: 'MAY', 6: 'JUNE', 7: 'JULY', 8: 'AUGUST', 9: 'SEPTEMBER',
                 10: 'OCTOBER', 11: 'NOVEMBER', 12: 'DECEMBER'}
        WDAY = {0: 'Sun', 1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat'}

        template_lines = template_file.readlines()
        for i in range(len(template_lines)):
            print(template_lines[i][:-1])

        samvatsara_id = (self.year - 1568) % 60 + 1  # distance from prabhava
        samvatsara_names = (NAMES['YEAR'][self.script][samvatsara_id],
                            NAMES['YEAR'][self.script][(samvatsara_id % 60) + 1])

        yname = samvatsara_names[0]  # Assign year name until Mesha Sankranti

        print('\\mbox{}')
        print('\\renewcommand{\yearname}{%d}' % self.year)
        print('\\begin{center}')
        print('{\\font\\x="Candara" at 60 pt\\x %d\\\\[0.5cm]}' % self.year)
        print('\\mbox{\\font\\x="Sanskrit 2003:script=deva" at 48 pt\\x %s–%s}\\\\[0.5cm]'
              % samvatsara_names)
        print('\\mbox{\\font\\x="Sanskrit 2003:script=deva" at 32 pt\\x %s } %%'
              % tr('kali', self.script))
        print('{\\font\\x="Candara" at 32 pt\\x %d–%d\\\\[0.5cm]}'
              % (self.year + 3100, self.year + 3101))
        print('{\\font\\x="Candara" at 48 pt\\x \\uppercase{%s}\\\\[0.2cm]}' % self.city.name)
        print('{\\font\\x="Candara" at 16 pt\\x {%s}\\\\[0.5cm]}'
              % print_lat_lon(self.city.latstr, self.city.lonstr))
        print('\hrule')
        print('\end{center}')
        print('\clearpage')

        for d in range(1, MAX_SZ - 1):

            [y, m, dt, t] = swe.revjul(self.jd_start + d - 1)

            # checking @ 6am local - can we do any better?
            local_time = tz(self.city.timezone).localize(datetime(y, m, dt, 6, 0, 0))
            # compute offset from UTC in hours
            tz_off = (datetime.utcoffset(local_time).days * 86400 +
                      datetime.utcoffset(local_time).seconds) / 3600.0

            # What is the jd at 00:00 local time today?
            jd = self.jd_start - (tz_off / 24.0) + d - 1

            tithi_data_str = ''
            for tithi_ID, tithi_end_jd in self.tithi_data[d]:
                # if tithi_data_str != '':
                #     tithi_data_str += '\\hspace{2ex}'
                tithi = '\moon[scale=0.8]{%d}~' % (tithi_ID) +\
                        NAMES['TITHI'][self.script][tithi_ID]
                if tithi_end_jd is None:
                    tithi_data_str = '%s\\mbox{%s {\\small\\RIGHTarrow} %s}' %\
                                     (tithi_data_str, tithi, tr('ahOrAtram', self.script))
                else:
                    tithi_data_str = '%s\\mbox{%s {\\small\\RIGHTarrow} \\textsf{%s%s}}' %\
                                     (tithi_data_str, tithi,
                                      time(24 * (tithi_end_jd - jd)).toString(format=self.fmt),
                                      '\\hspace{2ex}')

            nakshatram_data_str = ''
            for nakshatram_ID, nakshatram_end_jd in self.nakshatram_data[d]:
                if nakshatram_data_str != '':
                    nakshatram_data_str += '\\hspace{2ex}'
                nakshatram = NAMES['NAKSHATRAM'][self.script][nakshatram_ID]
                if nakshatram_end_jd is None:
                    nakshatram_data_str = '%s\\mbox{%s {\\small\\RIGHTarrow} %s}' %\
                                          (nakshatram_data_str, nakshatram,
                                           tr('ahOrAtram', self.script))
                else:
                    nakshatram_data_str = '%s\\mbox{%s {\\small\\RIGHTarrow} \\textsf{%s}}' %\
                                          (nakshatram_data_str, nakshatram,
                                           time(24 * (nakshatram_end_jd -
                                                      jd)).toString(format=self.fmt))

            rashi_data_str = ''
            for rashi_ID, rashi_end_jd in self.rashi_data[d]:
                # if rashi_data_str != '':
                #     rashi_data_str += '\\hspace{2ex}'
                rashi = NAMES['RASHI'][self.script][rashi_ID]
                if rashi_end_jd is None:
                    rashi_data_str = '%s\\mbox{%s}' % (rashi_data_str, rashi)
                else:
                    rashi_data_str = '%s\\mbox{%s \\RIGHTarrow \\textsf{%s}}' %\
                                     (rashi_data_str, rashi,
                                      time(24 * (rashi_end_jd - jd)).toString(format=self.fmt))
            if computeLagnams:
                lagna_data_str = 'लग्नं:~'
                for lagna_ID, lagna_end_jd in self.lagna_data[d]:
                    lagna = NAMES['MASA'][self.script][lagna_ID]
                    lagna_data_str = '%s \\mbox{%s \\RIGHTarrow \\textsf{%s}}' %\
                                     (lagna_data_str, lagna,
                                      time(24 * (lagna_end_jd - jd)).toString(format=self.fmt))

            yogam_data_str = ''
            for yogam_ID, yogam_end_jd in self.yogam_data[d]:
                # if yogam_data_str != '':
                #     yogam_data_str += '\\hspace{2ex}'
                yogam = NAMES['YOGAM'][self.script][yogam_ID]
                if yogam_end_jd is None:
                    yogam_data_str = '%s\\mbox{%s {\\small\\RIGHTarrow} %s}' %\
                                     (yogam_data_str, yogam, tr('ahOrAtram', self.script))
                else:
                    yogam_data_str = '%s\\mbox{%s {\\small\\RIGHTarrow} \\textsf{%s%s}}' %\
                                     (yogam_data_str, yogam,
                                      time(24 * (yogam_end_jd - jd)).toString(format=self.fmt),
                                      '\\hspace{2ex}')

            karanam_data_str = ''
            for numKaranam, (karanam_ID, karanam_end_jd) in enumerate(self.karanam_data[d]):
                # if numKaranam == 1:
                #     karanam_data_str += '\\hspace{2ex}'
                karanam = NAMES['KARANAM'][self.script][karanam_ID]
                if karanam_end_jd is None:
                    karanam_data_str = '%s\\mbox{%s {\\small\\RIGHTarrow} %s}' %\
                                       (karanam_data_str, karanam, tr('ahOrAtram', self.script))
                else:
                    karanam_data_str = '%s\\mbox{%s {\\small\\RIGHTarrow} \\textsf{%s%s}}' %\
                                       (karanam_data_str, karanam,
                                        time(24 * (karanam_end_jd - jd)).toString(format=self.fmt),
                                        '\\hspace{2ex}')

            sunrise = time(24 * (self.jd_sunrise[d] - jd)).toString(format=self.fmt)
            sunset = time(24 * (self.jd_sunset[d] - jd)).toString(format=self.fmt)
            moonrise = time(24 * (self.jd_moonrise[d] - jd)).toString(format=self.fmt)
            moonset = time(24 * (self.jd_moonset[d] - jd)).toString(format=self.fmt)

            pratahsandhya = time(24 * (self.kalams[d]['prAtaH sandhyA'][0] -
                                       jd)).toString(format=self.fmt)
            sangava = time(24 * (self.kalams[d]['saGgava'][0] - jd)).toString(format=self.fmt)
            madhyahna = time(24 * (self.kalams[d]['madhyAhna'][0] - jd)).toString(format=self.fmt)
            aparahna = time(24 * (self.kalams[d]['aparAhna'][0] - jd)).toString(format=self.fmt)
            sayahna = time(24 * (self.kalams[d]['sAyAhna'][0] - jd)).toString(format=self.fmt)
            sayamsandhya = time(24 * (self.kalams[d]['sAyaM sandhyA'][0] -
                                      jd)).toString(format=self.fmt)

            rahu = '%s--%s' % (
                time(24 * (self.kalams[d]['rahu'][0] - jd)).toString(format=self.fmt),
                time(24 * (self.kalams[d]['rahu'][1] - jd)).toString(format=self.fmt))
            yama = '%s--%s' % (
                time(24 * (self.kalams[d]['yama'][0] - jd)).toString(format=self.fmt),
                time(24 * (self.kalams[d]['yama'][1] - jd)).toString(format=self.fmt))
            gulika = '%s--%s' % (
                time(24 * (self.kalams[d]['gulika'][0] - jd)).toString(format=self.fmt),
                time(24 * (self.kalams[d]['gulika'][1] - jd)).toString(format=self.fmt))

            if self.solar_month[d] == 1:
                # Flip the year name for the remaining days
                yname = samvatsara_names[1]

            print('\caldata{%s}{%s}{%s{%s}{%s}{%s}}' %
                  (month[m], dt, self.month_data[d],
                   get_chandra_masa(self.lunar_month[d], NAMES, self.script),
                   NAMES['VARA'][self.script][self.weekday[d]], yname))
            print('{\\sunmoondata{%s}{%s}{%s}{%s}' % (sunrise, sunset, moonrise, moonset))
            print('{\kalas{%s}{%s}{%s}{%s}{%s}{%s}}}' % (pratahsandhya, sangava, madhyahna,
                                                         aparahna, sayahna, sayamsandhya,))
            if computeLagnams:
                print('{\\tnykdata{%s}%%\n{%s}{%s}%%\n{%s}%%\n{%s}{\\tiny %s}\n}'
                      % (tithi_data_str, nakshatram_data_str, rashi_data_str, yogam_data_str,
                         karanam_data_str, lagna_data_str))
            else:
                print('{\\tnykdata{%s}%%\n{%s}{%s}%%\n{%s}%%\n{%s}{\\tiny %s}\n}'
                      % (tithi_data_str, nakshatram_data_str, rashi_data_str, yogam_data_str,
                         karanam_data_str, ''))
            print('{\\rygdata{%s}{%s}{%s}}' % (rahu, yama, gulika))

            # Using set as an ugly workaround since we may have sometimes assigned the same
            # festival to the same day again!
            print('{%s}' % '\\eventsep '.join(
                [tr(f, self.script, True, True) for f in sorted(set(self.festivals[d]))]))

            print('{%s} ' % WDAY[self.weekday[d]])

            if m == 12 and dt == 31:
                break

        print('\end{document}')

    def computeIcsCalendar(self):
        with open('festival_rules.json') as festivals_data:
            festival_rules = json.load(festivals_data)

        self.ics_calendar = Calendar()
        uid_list = []
        for d in range(1, MAX_SZ - 1):
            [y, m, dt, t] = swe.revjul(self.jd_start + d - 1)

            if len(self.festivals[d]) > 0:
                # Eliminate repeat festivals on the same day, and keep the list arbitrarily sorted
                self.festivals[d] = sorted(list(set(self.festivals[d])))

                summary_text = self.festivals[d]
                # this will work whether we have one or more events on the same day
                for stext in sorted(summary_text):
                    if not stext.find('RIGHTarrow') == -1:
                        # It's a grahanam/yogam, with a start and end time
                        if stext.find('{}') != -1:
                            # Starting or ending time is empty, e.g. harivasara, so no ICS entry
                            continue
                        event = Event()
                        [stext, t1, arrow, t2] = stext.split('\\')
                        stext = stext.strip('~')
                        event.add('summary', tr(stext, self.script))
                        # we know that t1 is something like 'textsf{14:44}{'
                        # so we know the exact positions of min and hour
                        event.add('dtstart', datetime(y, m, dt, int(t1[7:9]), int(
                            t1[10:12]), tzinfo=tz(self.city.timezone)))
                        event.add('dtend', datetime(y, m, dt, int(t2[7:9]), int(
                            t2[10:12]), tzinfo=tz(self.city.timezone)))

                        stext_iast = str(transliterate(stext, 'harvardkyoto', 'iast'), 'utf8')
                        page_id = romanise(stext_iast).strip('-')
                        desc = ''
                        if stext in festival_rules:
                            desc = festival_rules[stext]['Short Description'] + '\n\n' +\
                                tr(festival_rules[stext]['Shloka'], self.script, False) + '\n\n'
                        else:
                            sys.stderr.write('No description found for festival %s!\n' % stext)
                        desc += "http://adyatithi.wordpress.com/" + page_id
                        event.add('description', desc.strip())
                        uid = '%s-%d-%02d' % (page_id, y, m)
                        if uid not in uid_list:
                            uid_list.append(uid)
                        else:
                            uid = '%s-%d-%02d-%02d' % (page_id, y, m, dt)
                            uid_list.append(uid)
                        event.add('uid', uid)
                        self.ics_calendar.add_component(event)
                    else:
                        event = Event()
                        event.add('summary', tr(stext.replace('~', ' '), self.script))
                        fest_num_loc = stext.find('#')
                        if not fest_num_loc == -1:
                            stext = stext[:fest_num_loc - 2] # Two more chars dropped, ~\
                        event.add('dtstart', date(y, m, dt))
                        event.add('dtend', (datetime(y, m, dt) + timedelta(1)).date())

                        stext_iast = str(transliterate(stext, 'harvardkyoto', 'iast'), 'utf8')
                        page_id = romanise(stext_iast).replace('/', '-').strip('-')

                        desc = ''
                        if stext.find('EkAdazI') == -1:
                            if stext in festival_rules:
                                desc = festival_rules[stext]['Short Description'] + '\n\n' +\
                                    tr(festival_rules[stext]['Shloka'], self.script, False) +\
                                    '\n\n'
                            else:
                                sys.stderr.write('No description found for festival %s!\n' % stext)
                            desc += "http://adyatithi.wordpress.com/" +\
                                page_id.rstrip('-1234567890').rstrip('0123456789{}\\#')
                        else:
                            # Handle ekadashi descriptions differently
                            ekad = '~'.join(stext.split('~')[1:])  # get rid of sarva etc. prefix!
                            if ekad in festival_rules:
                                desc = festival_rules[ekad]['Short Description'] + '\n\n' +\
                                    tr(festival_rules[ekad]['Shloka'], self.script) + '\n\n'
                            else:
                                sys.stderr.write('No description found for festival %s!\n' % ekad)
                            desc += '\n'

                        if page_id.find('ekadashi') != -1:
                            ekad = '-'.join(page_id.split('-')[1:-1])
                            # Skipping first split, which must be sarva/smarta/vaishnava
                            # Also skipping last, which is "ekadashi"
                            desc += "http://adyatithi.wordpress.com/" + ekad + "-ekadashi"
                        # print(page_id)
                        alarm = Alarm()
                        alarm.add('action', 'DISPLAY')
                        alarm.add('trigger', timedelta(hours=-4))
                        event.add_component(alarm)
                        event.add('description', desc.strip())
                        uid = '%s-%d-%02d' % (page_id, y, m)
                        if uid not in uid_list:
                            uid_list.append(uid)
                        else:
                            uid = '%s-%d-%02d-%02d' % (page_id, y, m, dt)
                            uid_list.append(uid)
                        event.add('uid', uid)
                        event['X-MICROSOFT-CDO-ALLDAYEVENT'] = 'TRUE'
                        event['TRANSP'] = 'TRANSPARENT'
                        event['X-MICROSOFT-CDO-BUSYSTATUS'] = 'FREE'
                        self.ics_calendar.add_component(event)

            if m == 12 and dt == 31:
                break

    def writeIcsCalendar(self, fname):
        ics_calendar_file = open(fname, 'wb')
        ics_calendar_file.write(self.ics_calendar.to_ical())
        ics_calendar_file.close()

    def writeDebugLog(self):
        log_file = open('cal-%4d-%s-log.txt' % (self.year, self.city.name), 'w')
        # MAX_SZ = 368
        for d in range(1, MAX_SZ - 1):
            jd = self.jd_start - 1 + d
            [y, m, dt, t] = swe.revjul(jd)
            longitude_sun_sunset = swe.calc_ut(
                self.jd_sunset[d], swe.SUN)[0] -\
                swe.get_ayanamsa(self.jd_sunset[d])
            log_data = '%02d-%02d-%4d\t[%3d]\tsun_rashi=%8.3f\ttithi=%8.3f\tsolar_month\
        =%2d\tlunar_month=%4.1f\n' % (dt, m, y, d, (longitude_sun_sunset % 360) / 30.0,
                                      get_angam_float(self.jd_sunrise[d], TITHI),
                                      self.solar_month[d], self.lunar_month[d])
            log_file.write(log_data)


if __name__ == '__main__':
    import doctest
    doctest.testmod(verbose=True)
