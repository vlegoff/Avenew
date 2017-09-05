"""Module containing the abstract representation."""

from evennia.utils.evform import EvForm

class BaseRepr(object):

    """Abstract representation."""

    fields = {}
    to_display = []
    form = None

    def __init__(self, obj):
        self.obj = obj

    def process(self, caller, field, value=None, operation="get"):
        """Process the data.  This is called by the 2 command.

        Args:
            caller (Object): the object calling for this modification.
            field (str): the field name.
            value (str, optional): the provided value, if any.
            operation (str, optional): the operation to perform. Can be
                    'get', 'set', 'clear', 'add', 'del'.

        Notes:
            The speicifed field can be in the field list (`fields`
            class variable).  If so, the value of the field in this
            class variable should be a type (like `int` or `str`).
            The methods `get_<field>`, `set_<field>`, `clear_<field>`,
            `add_<field>`, and `del_<field>` can also be provided for
            additional customization.

        """
        if not field:
            return self.display(caller)

        if value and field in type(self).fields and operation in ("set", "add", "del"):
            to_type = type(self).fields[field]
            try:
                value = to_type(value)
            except ValueError:
                caller.msg("Invalid value for {}: {}.".format(field, value))
                return

        # Different operations
        if operation == "get":
            if hasattr(self, "get_{}".format(field)):
                value = getattr(self, "get_{}".format(field))(caller)
            else:
                value = getattr(self.obj, field)
            caller.msg("Current value {} = {} for {}.".format(
                    field, value, self.obj.get_display_name(caller)))

    def display(self, caller):
        """Display the object."""
        if type(self).form:
            to_display = {}
            for i, field in enumerate(type(self).to_display):
                if hasattr(self, "get_{}".format(field)):
                    value = getattr(self, "get_{}".format(field))(caller)
                else:
                    value = getattr(self.obj, field)
                to_display[i + 1] = value
            caller.msg(EvForm(form={"CELLCHAR": "x", "TABLECHAR": "c",
                    "FORM": type(self).form}, cells=to_display))
        else:
            caller.msg("No display method has been provided for this object.")