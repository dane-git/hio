# -*- encoding: utf-8 -*-
"""
hio.core.doing Module
"""
from collections import deque

from ..hioing import ValidationError, VersionError
from ..help.timing import MonoTimer
from .basing import Ctl, Stt
from . import cycling



class Doer():
    """
    Base class for hierarchical structured async coroutines.
    Manages state based generator

    Attributes:
        .cycler is Cycler instance that provides relative cycle time as .cycler.tyme
                Ultimately a does at top level of run hierarchy are run by cycler
        .state is operational state of doer
        .desire is desired control for future iteration of generator
        .done is doer completion state True or False

    Properties:
        .tock is desired time in seconds between runs or until next run,
                 non negative, zero means run asap

    Methods:
        .do  runs its generator  with control parameter
        .makedo  makes or remakes its generator
        .enter perform enter context actions (open setup refresh etc)
        .recur perform recurring context actions (run, repeat)
        .exit perform exit context actions (close clean up tear down etc)

    Hidden:
       ._tock is hidden attribute for .tock property
       ._do is hidden attribute for generator
       ._doer is generator function

    """

    def __init__(self, cycler=None, tock=0.0):
        """
        Initialize instance.
        Parameters:
           cycler is Cycler instance
           tock is float seconds initial value of .tock

        """
        self.cycler = cycler or cycling.Cycler(tyme=0.0)
        self.tock = tock  # desired tyme interval between runs, 0.0 means asap

        self.state = Stt.exited  # operational state of doer
        self.desire = Ctl.exit  # desired control next time Task is iterated
        self.done = True  # doer completion state reset on restart
        self.makedo()  # make generator assign to .run and advance to yield


    @property
    def tock(self):
        """
        tock property getter, get ._tock
        .tock is float desired .tyme increment in seconds
        """
        return self._tock


    @tock.setter
    def tock(self, tock):
        """
        desired cycle tyme interval until next run
        0.0 means run asap,
        set ._tock to tock
        """
        self._tock= abs(float(tock))


    def makedo(self):
        """
        Make and assign generator and advance to first yield
        .send(None) same as .next()
        """
        self._do = self._doer() # make generator
        state = self._do.send(None) # run to first yield and accept default status
        # next .send(control) results in first control being accepted at yield


    def do(self, control):
        """
        Returns state from iteration of generator .do after  send of control
        """
        return(self._do.send(control))


    def _doer(self):
        """
        Generator function to run this doer
        Returns generator

        Simplified state machine switch on control not state
        has less code because of defaults that just ignore control
        when it's not applicable to current state
        Status cycles:
            exited -> entered -> recurring -> exited
            exited -> entered -> recurring -> ...
            exited -> entered -> ...
            exited -> entered -> exited -> entered -> ...
            exited -> entered -> recurring -> exited -> entered -> ...

            exited -> aborted
            exited -> entered -> exited -> aborted
            exited -> entered -> recurring -> exited -> aborted


        """
        self.desire = Ctl.exit  # default what to do next time, override below
        self.state = Stt.exited # operational state of doer
        self.done = True

        try:
            while (True):
                # waits after yield of state for .send to accept new control
                control = (yield (self.state))

                if control == Ctl.recur:  # Want recur and recurring state
                    if self.state in (Stt.entered, Stt.recurring):  # Want recur
                        self.recur()  # .recur may change .desire for next run
                        self.state = Stt.recurring  # stay in recurring

                    elif self.state in (Stt.exited, ):  #  Auto enter on recur in exited
                        self.done = False   # .done may change in .enter, .recur, or .exit
                        self.enter()  # may change .desire for next run
                        self.state = Stt.entered
                        self.recur()  # may change .desire for next run
                        self.state = Stt.recurring

                    else:  # bad state for control
                        break  # break out of while loop. Forces stopIteration

                elif control == Ctl.enter:  # Want enter and entered state
                    if self.state in (Stt.exited, ):  # enter only after exit
                        self.done = False  # .done may change in .enter, .recur, or .exit
                        self.enter()  # may change .desire for next run
                        self.state = Stt.entered

                    elif self.state in  (Stt.recurring, ):  # want exit and reenter
                        # forced reenter without exit so must force exit first
                        self.exit(forced=True)  # do not set .done. May change .desire
                        self.state = Stt.exited
                        self.done = False  # .done may change in .enter, .recur, or .exit
                        self.enter()
                        self.state = Stt.entered

                    elif self.state in  (Stt.entered, ):  # already entered
                        pass  # redundant

                    else:  # bad state for control
                        break  # break out of while loop. Forces stopIteration

                elif control == Ctl.exit:  # Want exit and exited state
                    if self.state in (Stt.entered, Stt.recurring):
                        # clean exit so .done set to True
                        self.exit()  # may change.desire
                        self.state = Stt.exited
                        self.desire = Ctl.exit  #  stay in exited

                    elif self.state in  (Stt.exited, ):  # already exited
                        pass  # redundant

                    else:  # bad state for control
                        break  # break out of while loop. Forces stopIteration

                else :  # control == Ctl.abort or unknown.  Want aborted state
                    if self.state in (Stt.entered, Stt.recurring):  # force exit
                        self.exit(forced=True)  # do not set .done. May change .desire
                        self.state = Stt.exited
                    self.state = Stt.aborted
                    self.desire = Ctl.abort
                    break  # break out of while loop. Forces stopIteration

        finally:  # in case uncaught exceptio
            if self.state in (Stt.entered, Stt.recurring):  # force exit
                self.exit(forced=True)  # do not set .done. May change .desire
                self.state = Stt.exited
            self.state = Stt.aborted
            self.desire = Ctl.abort


    def enter(self):
        """
        Placeholder, Override in sub class
        """

    def recur(self):
        """
        Placeholder, Override in sub class
        """

    def exit(self, forced=False):
        """
        Placeholder, Override in sub class

        forced is boolean. True means forced exit, Otherwise false.
            Only set .done to True if not a forced exit
        """

        if not forced:  # clean unforced exit sets .done to True
            self.done = True


