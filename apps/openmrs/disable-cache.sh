#!/bin/sh
# DB-level restores bypass Hibernate. Disable its caches (the CATALINA_OPTS in compose.yml alone is not honoured)
# and restart the app once. Run after the first successful start.
docker exec openmrs-openmrs-1 sh -c 'printf "\nhibernate.cache.use_second_level_cache=false\nhibernate.cache.use_query_cache=false\nhibernate.cache.use_structured_entries=false\n" >> /usr/local/tomcat/.OpenMRS/openmrs-runtime.properties'
docker restart openmrs-openmrs-1
