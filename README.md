# Overview
Welcome to the Adherence Starts with Knowledge - 12 (ASK-12) Comprehensive tool, written collaboratively in BMI-507 at the University of Buffalo.<br>
A proof-of-concept (POC) can be found deployed on shinyapps.io here: https://adherencestartswithknowledge12ubuffalo.shinyapps.io/ask-12/<br><br>
Authors include (in alphabetical order):<br>
Vida Bodaghinamileh<br>
Stephen Granite<br>
Jahanzab Salim<br>
Inev Vemury<br>

# Purpose
ASK-12 is a brief, 12-item validated questionnaire designed to identify patient-specific barriers to medication adherence (https://eprovide.mapi-trust.org/instruments/adherence-starts-with-knowledge-12). It was developed and web-enabled by GlaxoSmithKline Research and Development Limited (GSK). It is a shortened, practical version of the Adherence Starts with Knowledge 20 (ASK-20) survey focusing on three main domains: inconvenience/forgetfulness, treatment beliefs, and behavior.  The ASK-20 is a validated, 20-item patient-reported survey designed to identify specific barriers to medication adherence across chronic diseases (https://www.sralab.org/rehabilitation-measures/adherence-starts-knowledge-20). Both are intended to evaluate patient behaviors and beliefs to identify why they may not follow a prescribed treatment plan.

Both of the implementations above allow for medical teams to get answers regarding adherence. ASK-20, however, is solely a paper form and requires manual interpretation by the medical team. GSK's ASK-12 implementation is publicly available, but requires an account creation and other settings for use. Our implementation is to provide a platform-agnostic tool (i.e., it works on all browsers on computers, tablets and smart phones). It can be utilized by  both the subject and the medical team. It persists subject information in an encrypted manner in this POC implementation, ensuring patient privacy. Both the encryption pattern and the password are maintained in a properties file. The properties file shown here is empty to ensure that the version publicly available for use and feedback is secured in its deployment.

# Prerequisites
shiny 						<- Necessary to use Shiny For Python in deployment<br>
shiny_validate			<- Helps to validate entries by the subject, ensuring that they fill out the entire form<br>
pandas						<- Utilized to organize data and read/write from CSV used in POC<br>
rsconnect-python		<- Necessary to deploy to shinyapps.io for POC implementation<br>

# Deployment

