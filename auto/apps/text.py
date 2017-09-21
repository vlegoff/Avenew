"""
Text application.

This app allows to send text, and see what texts have been received.
Texts are grouped by threads.  A thread is a list of messages sharing
the same users participating in the conversation.  For instance, if
A sends a message to B, and B a message to A, both messages will belong
to the same thread.

When a user enters into the text appl, she will see the list of threads
(of conversations that she participated to).  She can open one of these
threads by entering a number.  This will display the most recent messages
in the thread (both that she sent and received).  It will also allow
her to directly respond to the thread (all other users in the conversation
will see this new message).

Screens in this app:
    MainScreen: the main screen, displaying the list of threads as
            numbers.  The user can enter a number to open this thread
            and reply to it.
    ThreadScreen: the screen allowing to visualize a thread with its most
            recent messages, and to reply to it.
    NewTextScreen: the screen allowing to send a new text independent of any thread.

Commands in this app:
    MainScreen:
        new: create a new message outside of a thread (CmdNew).
    ThreadScreen:
        send: send the content of the reply to the thread (CmdSend).
    NewTextScreen:
        to: add or remove a contact or phone number as recipient (CmdTo).
        send: send the message (CmdSend).
        cancel: cancel (CmdCancel).

Note:
    Texts aren't stored in the application itself.  To allow greater
    speed in retrieving (and more advanced searching), texts are
    saved in a specific model, along with threads.  To see the mechanism,
    visit `web.text`.

"""

from textwrap import dedent, wrap

from evennia import search_tag
from evennia.utils.utils import crop, lazy_property

from auto.apps.base import BaseApp, BaseScreen, AppCommand
from web.text.models import Text, Thread

## Helper functions
def get_phone_number(obj):
    """Return the phone number of this object, if found."""
    number = obj.tags.get(category="phone number")
    if not number or not isinstance(number, basestring):
        raise ValueError("unknown or invalid phone number")

    number = number[:3] + "-" + number[3:]
    return number

## New text screen and commands

class CmdSend(AppCommand):

    """
    Send the current text message.

    Usage:
        send

    This will send the text message on your screen to the selected
    recipients, who might already be members of the conversation.
    """

    key = "send"

    def func(self):
        """Execute the command."""
        screen = self.screen
        db = screen.db
        sender = screen.obj.tags.get(category="phone number")
        recipients = list(db.get("recipients", []))
        if not recipients:
            self.msg("You haven't specified at least one recipient.")
            screen.display()
            return

        content = db["content"]
        if not content:
            self.msg("This text is empty, write something before sending it.")
            screen.display()
            return

        # Send the new text
        text = Text.objects.send(sender, recipients, content)
        for number in text.list_recipients:
            devices = search_tag(number, category="phone number")
            for device in devices:
                types = device.types.has("notifications")
                if types:
                    name = sender
                    computer = device.types.get("computer")
                    if computer:
                        contact = computer.apps.get("contact")
                        if contact:
                            name = contact.format(sender)

                    types[0].notifications.add("New text from {}".format(name),
                            "auto.apps.text.ThreadScreen", "text", content=content,
                            db=dict(thread=text.thread), alert=True)

        self.msg("Thanks, your message has been sent successfully.")
        if screen.db.get("go_back", True):
            screen.back()
        else:
            screen.display()


class CmdCancelSend(AppCommand):

    """
    Cancel and go back to the list of texts.

    Usage:
        cancel
    """

    key = "cancel"

    def func(self):
        """Execute the command."""
        screen = self.screen
        self.msg("Your text was cancelled.  Going back to the list of texts.")
        screen.back()


class CmdTo(AppCommand):

    """
    Add or remove a recipient.

    Usage:
        to <phone number or contact>

    If the phone number, or contact, is already present, remove it.

    Usage:
        to 555-1234

    If your device has access to a contact app, you can add and remove
    recipients by their names:

    Usage:
        to Martin

    You don't have to specify the full name of the contact.  If more than one
    contact matches the letters you have specified, you will be given the list
    of possibilities and will have to specify more letters next time.
    """

    key = "to"

    def func(self):
        """Execute the command."""
        screen = self.screen
        db = screen.db
        number = self.args.strip()
        if not number:
            self.msg("Specify a phone number or contact name of a recipient, to add or remove him.")
            return

        # First of all, maybe it's a contact name
        if screen.app.contact:
            matches = screen.app.contact.search(number)
            if len(matches) == 1:
                number = matches[0].phone_number
            elif len(matches) >= 2:
                self.msg("This contact name isn't specific enough.  It could be:\n  {}\nPlease specify.".format("  ".join([contact.name for contact in matches])))
                return

        number = number.replace("-", "")
        if not number.isdigit() or len(number) != 7:
            self.msg("This is not a valid phone number.")
            return

        # Add or remove
        if "recipients" not in db:
            db["recipients"] = []
        recipients = db["recipients"]
        if number in recipients:
            recipients.remove(recipient)
            self.msg("This phone number was removed from the list of recipients.")
        else:
            recipients.append(number)
            self.msg("This phone number was added to the list of recipients.")
        screen.display()


class NewTextScreen(BaseScreen):

    """This screen appears to write a new message, with possibly some
    fields that are pre-loaded.  This screen will appear to create
    a new message independent of any thread.  Note, however, that if
    the list of recipients matches a previous conversation, the new
    message will simply be appended to this previous thread.

    Data attributes you can use (in screen.db):
        recipients: a list of phone numbers representing the list of recipients.
        content: the new text content as a string.

    """

    commands = [CmdSend, CmdCancelSend, CmdTo]
    back_screen = "auto.apps.text.MainScreen"

    def display(self):
        """Display the new message screen."""
        number = get_phone_number(self.obj)
        screen = dedent("""
            New message (|lcback|ltBACK|le to go back, |lcexit|ltEXIT|le to exit)

            From: {}
              To: {}

            Text message:
                {}

                |lcsend|ltSEND|le                                             |lccancel|ltCANCEL|le
        """.lstrip("\n"))
        db = self.db
        recipients = list(db.get("recipients", []))
        for i, recipient in enumerate(recipients):
            if self.app.contact:
                recipients[i] = self.app.contact.format(recipient)

        content = db.get("content", "(type your text here)")
        content = "\n    ".join(wrap(content, 75))
        recipients = ", ".join(recipients)
        self.user.msg(screen.format(number, recipients, content))

    def no_match(self, string):
        """Command no match, to write the text content."""
        db = self.db
        old_content = db.get("content", "")
        if old_content:
            old_content += "\n"
        content = old_content + string
        db["content"] = content
        self.display()
        return True


## Thread screen and commands

class CmdContact(AppCommand):

    """
    Open the contact dialog for a recipient in this conversation.

    Usage:
        contact [number]

    This command will open the contact dialog for the recipient in the current
    conversation.  This will allow to create a new contact if the recipient has
    none yet.  If more than one recipient are present in this conversation, the |hCONTACT|n
    command will show you a list of possible contacts in a numbered list, and ask you to enter
    |hCONTACT|n followed by the number of the contact you want to open.  For instance:

        contact 2
    """

    key = "contact"

    def func(self):
        """Execute the command."""
        screen = self.screen
        recipients = list(screen.db.get("recipients", []))
        if not recipients:
            self.msg("There are no recipient in this conversation yet.  Use the |hTO|n command to add recipients.")
            return

        contact_app = screen.type.apps.get("contact")
        if not contact_app:
            self.msg("You do not have the contact application.")
            return

        if len(recipients) == 1:
            recipient = recipients[0]
            screen, db = contact_app.edit(recipient)
            self.screen.next(screen, contact_app, db=db)
            return

        # Otherwise, choose a contact
        args = self.args.strip()
        if not args:
            string = "Specify a contact number after |hCONTACT|n:\n"
            for i, recipient in enumerate(recipients):
                string += "\n{|: {}".format(i, contact_app.format(recipient, False))
                self.msg(string)

        # Try to get the recipient
        try:
            args = int(args)
            assert args > 0
            recipient = recipients[args]
        except (ValueError, AssertionError, IndexError):
            self.msg("Invalid contact number.")
        else:
            screen, db = contact_app.edit(recipient)
            screen.next(screen, "contact", db=db)


class ThreadScreen(BaseScreen):

    """This screen appears to see a specific thread and allow to
    write and reply right away.

    Data attributes you can use (in screen.db):
        thread: the thread object (`web.text.models.Thread`).

    """

    commands = [CmdSend, CmdContact]
    back_screen = "auto.apps.text.MainScreen"

    def display(self):
        """Display the new message screen."""
        db = self.db
        db["go_back"] = False
        thread = db["thread"]
        if not thread:
            self.user.msg("Can't display the thread, an error occurred.")
            return

        number = self.obj.tags.get(category="phone number")
        screen = dedent("""
            Messages with {} (|lcback|ltBACK|le to go back, |lcexit|ltEXIT|le to exit)
            |lccontact|ltCONTACT|le to edit the contact for this conversation.

            {}

            Text message:
                {}

                |lcsend|ltSEND|le
        """.lstrip("\n"))
        texts = list(reversed(thread.text_set.order_by("db_date_sent").reverse()[:10]))
        if texts:
            recipients = texts[0].exclude(number)
            db["recipients"] = recipients
            if self.app.contact:
                recipients = [self.app.contact.format(recipient) for recipient in recipients]

        # Browse the list of texts in this thread
        messages = []
        for text in texts:
            sender = text.sender
            if sender == number:
                sender = "You"
            elif self.app.contact:
                sender = self.app.contact.format(sender)

            content = text.content + " (" + text.sent_ago + ")"
            content = wrap(content, 75 - len(sender) - 3)
            content = ("\n" + (len(sender) + 2) * " ").join(content)
            messages.append(sender + ": " + content)

        content = db.get("content", "(type your text here)")
        content = "\n    ".join(wrap(content, 75))
        recipients = ", ".join(recipients)
        messages = "\n".join(messages)
        self.user.msg(screen.format(recipients, messages, content))

    def no_match(self, string):
        """Command no match, to write the text content."""
        db = self.db
        old_content = db.get("content", "")
        if old_content:
            old_content += "\n"
        content = old_content + string
        db["content"] = content
        self.display()
        return True


## Main screen and commands

class CmdNew(AppCommand):

    """
    Compose a new text message.

    Usage:
        new
    """

    key = "new"

    def func(self):
        self.screen.next(NewTextScreen)


class MainScreen(BaseScreen):

    """Main screen of the text app.

    This screen displays the text messages, both sent and received
    by this phone, as a list of conversations (or threads).  It provides
    commands to create new messages, and open them in a separate screen.

    Data attributes you can use (in screen.db):
        none

    """

    commands = [CmdNew]
    back_screen = "auto.apps.base.MainScreen"

    def display(self):
        """Display the app."""
        number = self.obj.tags.get(category="phone number")
        if not number or not isinstance(number, basestring):
            self.msg("Your phone number couldn't be found.")
            self.back()
            return

        threads = Text.objects.get_threads_for(number)
        string = "Texts for {} (|lcback|ltBACK|le to go back, |lcexit|ltEXIT|le to exit)".format(number)
        string += "\n"
        self.db["threads"] = {}
        stored_threads = self.db["threads"]
        if threads:
            string += "  Create a |lcnew|ltNEW|le message.\n"
            i = 1
            for thread_id, text in threads.items():
                thread = text.thread
                stored_threads[i] = thread
                senders = text.exclude(number)
                if self.app.contact:
                    senders = [self.app.contact.format(sender) for sender in senders]

                sender = ", ".join(senders)
                if thread.name:
                    sender = thread.name
                sender = crop(sender, 20)

                content = text.content
                if text.sender == number:
                    content = "]You] " + content
                content = crop(content, 35)
                string += "\n  {{|lc{i}|lt{i:>2}|le}} {:<20}: {:<35} ({}(".format(sender, content, text.sent_ago, i=i)
                i += 1
            string += "\n\n(Type a number to open this text.)"
        else:
            string += "\n  You have no texts yet.  Want to create a |lcnew|ltNEW|le one?"

        count = Text.objects.get_texts_for(number).count()
        s = "" if count == 1 else "s"
        string += "\n\nText app: {} saved message{s}.".format(count, s=s)
        self.user.msg(string)

    def no_match(self, string):
        """Method called when no command matches the user input.

        This allows us to redirect to the ThreadScreen if a number
        has been entered.

        """
        if string.isdigit():
            thread = int(string)
            if thread not in self.db["threads"]:
                self.user.msg("This is not a number in your current threads.")
                self.display()
            else:
                thread = self.db["threads"][thread]
                self.next(ThreadScreen, db=dict(thread=thread))

            return True

        return False

    def wrong_input(self, string):
        """A wrong input has been entered."""
        self.user.msg("Enter a thread number to oepn it.")


class TextApp(BaseApp):

    """Text applicaiton.

    This class defines the application for texting.  It doesn't contain
    many things, as most features are defined in the screen themselves.

    """

    app_name = "text"
    start_screen = MainScreen

    @lazy_property
    def contact(self):
        """Return the contact app, if available."""
        return self.type.apps.get("contact")
