# This is a sample Python script.
import re

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import pandas as pd
import calendar


def main(df):

    # Infos from csv
    participants = (df.shape[1]-4)  # number of participants
    month = int(df.month[0])
    year = int(df.year[0])
    total_days = calendar.monthrange(year, month)[1]
    # check if the total number of days is correct in the input table
    if total_days != df.shape[0]:
        print("ATTENTION!! The month of", calendar.month_name[month], "has", total_days, "days!")
        quit()

    # Infos on shift count and constraints
    total_shifts = 2 * total_days
    aver_shifts_per_person = round(total_shifts / participants)
    constraints = df.drop(["year", "month", "day", "weekday"], axis=1)
    constraints.index = [i for i in range(1,total_days+1)]

    # Names of participants
    participants_names = list(constraints.columns.values)

    # Dataframe for number of shift per person
    data = [aver_shifts_per_person]*len(participants_names)
    shifts_per_person = pd.DataFrame(columns=participants_names)
    shifts_per_person.loc[0] = data  # dataframe of average number of shifts per person
    shifts_per_person.loc[1] = [0] * participants  # add line for vacation days
    shifts_per_person.loc[2] = [0] * participants  # add line for maximum shifts per person
    shifts_per_person.loc[3] = [0] * participants  # add line for total shifts after scheduled
    shifts_per_person.loc[4] = [0] * participants  # add line for total shifts in weekends after scheduled
    shifts_per_person.index = ['Average', 'Vacation', 'Maximum', 'Total', 'Total_weekends']

    # Dataframe for shift schedule OUTPUT
    data = {'weekday': list(df.weekday),
            'daytime': [0]*total_days,
            'nighttime': [0]*total_days}  # blank dict
    schedule = pd.DataFrame(data)  # blank dataframe for schedule output
    schedule.index = [i for i in range(1, total_days + 1)]

    # Count vacation shifts to be redistributed
    column_list = list(constraints.columns.values)  # column names of people on vacation this month
    people_on_vacation = []
    for column in column_list:
        vacation_shifts = round((constraints[column].squeeze().str.contains('(?i)Vacation', regex=True).sum()/total_days)
                                * aver_shifts_per_person)  # proportion of shifts lost due to vacation
        shifts_per_person[column].iloc[1] = vacation_shifts  # update shifts dataframe
        shifts_per_person[column].iloc[2] = aver_shifts_per_person - vacation_shifts  # maximum shifts subtracting

        if constraints[column].squeeze().str.contains('(?i)Vacation', regex=True).any():
            people_on_vacation.append(column)  # vacation ones

    # Replace "vacation" by "0;0" and create constraints dataframes for daytime and nighttime
    constraints = constraints.replace('(?i)Vacation', '0;0', regex=True)  # case insensitive replacement
    constraints_day = constraints.apply(lambda x: x.str.split(';', expand=True).astype(int)[0])
    constraints_night = constraints.apply(lambda x: x.str.split(';', expand=True).astype(int)[1])

    # Define maximum number of shifts per person
    no_vacation = [col for col in constraints.columns if col not in people_on_vacation]  # people not on vacation
    shifts_per_person.loc['Maximum', no_vacation] = round(aver_shifts_per_person + shifts_per_person.iloc[1].sum()/
                                                    (participants-len(people_on_vacation)))  # Maximum number of shifts

    # First day of the month -> first shift for the same person in the last from last month
    # Count total weekend shifts
    weekdays = ['(?i)Saturday|(?i)Sunday',
                '(?i)Monday|(?i)Tuesday|(?i)Wednesday|(?i)Thursday|(?i)Friday']  # weekends and business days
    weekend_shifts_total = 2*schedule.index[schedule['weekday'].str.contains(weekdays[0], regex=True)].size

    # Friday is not considered a weekend day
    # Start from the weekends, which must be distributed equally
    for i in [0, 1]:

        # Choose days
        days_week = list(schedule.index[schedule['weekday'].str.contains(weekdays[i], regex=True)].values)

        for dayofmonth in days_week:

            # search people available
            person2 = ''
            people = constraints_day.columns[constraints_day.loc[dayofmonth].eq(1)]
            shifts = shifts_per_person.loc['Total']/shifts_per_person.loc['Maximum']
            shifts_weekend = shifts_per_person.loc['Total_weekends']/weekend_shifts_total

            # if it is the first scheduling, choose the one with less availability
            if shifts_per_person.loc['Total'].sum() == 0:
                person = constraints_day[people].sum().idxmin()  # person w/ smallest sum of days available
            else:
                if i == 0:  # weekend day
                    # choose the person with fewer shifts on weekend
                    person = shifts_weekend[people].nsmallest(1).index.tolist()[0]
                else:  # not weekend day
                    # choose the one with fewer shifts scheduled with regard to the maximum number of shifts per person
                    person = shifts[people].nsmallest(1).index.tolist()[0]

            if dayofmonth == 1:
                # just schedule first shift of the month for the last person of past month
                schedule.loc[dayofmonth, 'daytime'] = person
                shifts_per_person.loc['Total', person] += 1  # add shifts for this person

            else:  # for all other days of the month
                # check if person can make 24h shift and schedule
                if constraints_night.loc[dayofmonth - 1, person] == 1:
                    # schedule person for 24 hours
                    pass

                # check if person cannot make 24h and schedule another for the night
                elif constraints_night.loc[dayofmonth - 1, person] == 0:
                    people_available = constraints_night.columns[constraints_night.loc[dayofmonth - 1].eq(1)]

                    shifts = shifts_per_person.loc['Total']/shifts_per_person.loc['Maximum']
                    person2 = shifts[people_available].nsmallest(1).index.tolist()[0]

                if person2 == '':
                    schedule.loc[dayofmonth, 'daytime'] = person
                    schedule.loc[dayofmonth - 1, 'nighttime'] = person
                    shifts_per_person.loc['Total', person] += 2  # add shifts for this person
                else:
                    schedule.loc[dayofmonth, 'daytime'] = person
                    shifts_per_person.loc['Total', person] += 1  # add shift for this person
                    schedule.loc[dayofmonth - 1, 'nighttime'] = person2
                    shifts_per_person.loc['Total', person2] += 1  # add shift for this person

            # update constraints
            if person2 == '':

                # update constraints for 24h shift, 1 person (48-hour rest)
                if dayofmonth > 1:
                    constraints_day.loc[dayofmonth - 1, person] = 0
                    if dayofmonth > 2:
                        constraints_day.loc[dayofmonth - 2, person] = 0
                        constraints_night.loc[dayofmonth - 2, person] = 0
                        if dayofmonth > 3:
                            constraints_night.loc[dayofmonth - 3, person] = 0

                constraints_night.loc[dayofmonth, person] = 0
                if dayofmonth < total_days:
                    constraints_day.loc[dayofmonth + 1, person] = 0
                    constraints_night.loc[dayofmonth + 1, person] = 0
                    if dayofmonth < total_days - 1:
                        constraints_day.loc[dayofmonth + 2, person] = 0

            else:
                # update constraints for 12h shift, 2 people (24-hour rest each)
                constraints_night.loc[dayofmonth, person] = 0
                constraints_day.loc[dayofmonth, person2] = 0
                constraints_night.loc[dayofmonth, person2] = 0

                if dayofmonth > 1:
                    constraints_day.loc[dayofmonth - 1, person] = 0
                    constraints_night.loc[dayofmonth - 1, person] = 0
                    constraints_day.loc[dayofmonth - 1, person2] = 0
                    if dayofmonth > 2:
                        constraints_night.loc[dayofmonth - 2, person2] = 0

                if dayofmonth < total_days:
                    constraints_day.loc[dayofmonth + 1, person] = 0

            # after the selection, check if any person has already achieved the maximum number of shifts
            max_achieved = list(shifts_per_person.columns.values[shifts_per_person.loc['Maximum']
                                                            - shifts_per_person.loc['Total'] <= 0])
            constraints_day[max_achieved] = 0  # zeros in all the days for those who already achieved maximum shifts
            constraints_night[max_achieved] = 0

            # for the last night shift of the month
            if dayofmonth == total_days:
                # search people available
                people = constraints_night.columns[constraints_night.loc[dayofmonth].eq(1)]
                shifts = shifts_per_person.loc['Total']/shifts_per_person.loc['Maximum']
                shifts_weekend = shifts_per_person.loc['Total_weekends'] / weekend_shifts_total
                if i == 0:  # weekend day
                    # choose the person with fewer shifts on weekend
                    person = shifts_weekend[people].nsmallest(1).index.tolist()[0]
                else:  # not weekend day
                    # choose the one with fewer shifts scheduled with regard to the maximum number of shifts per person
                    person = shifts[people].nsmallest(1).index.tolist()[0]
                schedule.loc[dayofmonth, 'nighttime'] = person
                shifts_per_person.loc['Total', person] += 1  # add shifts for this person

            # check the number of weekend shifts for each
            if i == 0:
                shifts_per_person.loc['Total_weekends', person] = schedule[schedule['weekday'].str.contains(weekdays[0],
                                                 regex=True).values].daytime.value_counts().fillna(0).get(person,0)
                shifts_per_person.loc['Total_weekends', person] += schedule[schedule['weekday'].str.contains(weekdays[0],
                                                 regex=True).values].nighttime.value_counts().fillna(0).get(person,0)
                if person2 != '':
                    shifts_per_person.loc['Total_weekends', person2] = schedule[schedule['weekday'].str.contains(
                        weekdays[0], regex=True).values].daytime.value_counts().fillna(0).get(person2,0)
                    shifts_per_person.loc['Total_weekends', person2] += schedule[schedule['weekday'].str.contains(
                        weekdays[0], regex=True).values].nighttime.value_counts().fillna(0).get(person2,0)

            print(schedule)
            print(shifts_per_person)
            print(constraints_day)
            print(constraints_night)

    # answer
    return schedule, shifts_per_person


# main line
if __name__ == '__main__':

    # Read data file
    df = pd.read_csv('conditions.csv')

    # Execute program
    schedule, shifts_per_person = main(df)

    # print answers in csv
    file = 'shifts.csv'
    schedule.to_csv(file, index=True)
    shifts_per_person.to_csv(file, mode='a')

    print(schedule)
    print(shifts_per_person)