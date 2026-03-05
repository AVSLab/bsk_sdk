/*
 ISC License

 Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder

 Permission to use, copy, modify, and/or distribute this software for any
 purpose with or without fee is hereby granted, provided that the above
 copyright notice and this permission notice appear in all copies.

 THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

 */


%module customExponentialAtmosphere

%include "architecture/utilities/bskException.swg"
%default_bsk_exception();

%{
    #include "customExponentialAtmosphere.h"
%}

%pythoncode %{
from Basilisk.architecture.swig_common_model import *
%}
%include "swig_conly_data.i"
%include "std_vector.i"
%include "std_string.i"

// IMPORTANT: use %import (not %include) for Basilisk base-class modules.
//
// %import tells SWIG "these types live in an existing Python module — do not
// re-wrap them here."  The generated Python class for this plugin will then
// inherit from Basilisk's cSysModel.SysModel, which is what Basilisk's
// simulation task manager expects when you call AddModelToTask().
//
// Using %include instead creates a *separate* SysModel type inside this
// module that is invisible to Basilisk's type system, causing a confusing
// runtime TypeError even though the C++ inheritance is correct.
%import "sys_model.i"

// Intermediate base classes that are NOT exposed by any Basilisk Python
// module can still be %included — SWIG wraps them locally and they inherit
// from the imported SysModel above, keeping the full chain intact.
%include "simulation/environment/_GeneralModuleFiles/atmosphereBase.h"
%include "customExponentialAtmosphere.h"

%include "architecture/msgPayloadDefC/SpicePlanetStateMsgPayload.h"
struct SpicePlanetStateMsg_C;
%include "architecture/msgPayloadDefC/SCStatesMsgPayload.h"
struct SCStatesMsg_C;
%include "architecture/msgPayloadDefC/AtmoPropsMsgPayload.h"
struct AtmoPropsMsg_C;

// Plugin-defined message
%include "CustomAtmStatusMsgPayload.h"
struct CustomAtmStatusMsg_C;

%pythoncode %{
import sys
protectAllClasses(sys.modules[__name__])
%}
