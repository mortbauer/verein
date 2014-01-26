import cerberus


class Validator(cerberus.Validator):
    """ A cerberus.Validator subclass adding the `unique` contraint to
    Cerberus standard validation.

    :param schema: the validation schema, to be composed according to Cerberus
                   documentation.
    :param resource: the resource name.

    .. versionchanged:: 0.0.6
       Support for 'allow_unknown' which allows to successfully validate
       unknown key/value pairs.

    .. versionchanged:: 0.0.4
       Support for 'transparent_schema_rules' introduced with Cerberus 0.0.3,
       which allows for insertion of 'default' values in POST requests.
    """
    def __init__(self, schema,**kwargs):
        super(Validator, self).__init__(schema, transparent_schema_rules=True,**kwargs)

    def _validate_forbidden(self, forbidden, field, value):
        if value in forbidden:
            self._error(field,"value '%s' is forbidden"%value)

