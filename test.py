            try:
                applicant_data['location'] = application['vacancy']['localityTitle']
            except:
                applicant_data['location'] = "Москва"

